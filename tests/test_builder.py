import math
from enum import Enum, auto
from operator import ne
from typing import List, Optional, Type, Union

from netqasm.lang.ir import BranchLabel, GenericInstr, ICmd, PreSubroutine
from netqasm.logging.glob import get_netqasm_logger, set_log_level
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.qubit import Qubit

logger = get_netqasm_logger()


class PatternWildcard(Enum):
    ANY_ONE = auto()
    ANY_ZERO_OR_MORE = auto()
    BRANCH_LABEL = auto()


class PatternMatcher:
    def __init__(
        self, commands: List[ICmd], pattern: List[Union[GenericInstr, PatternWildcard]]
    ) -> None:
        self._commands = commands
        self._pattern = pattern

        self._pat_len: int = len(self._pattern)
        self._pat_idx: int = 0
        self._cmd_idx: int = 0
        self._match_start: Optional[int] = None

    def _record_match(self) -> None:
        if self._match_start is None:
            self._match_start = self._cmd_idx
        self._pat_idx += 1

    def _reset_match(self) -> None:
        self._match_start = None
        self._pat_idx = 0

    def _match_any_one(self) -> None:
        logger.debug("\tmatching ANY_ONE")
        self._record_match()

    def _match_branch_label(self) -> None:
        cmd = self._commands[self._cmd_idx]
        if isinstance(cmd, BranchLabel):
            logger.debug("\tmatching BranchLabel")
            self._record_match()
        else:
            self._reset_match()

    def _match_instr(self) -> None:
        pat = self._pattern[self._pat_idx]
        assert isinstance(pat, GenericInstr)

        cmd = self._commands[self._cmd_idx]
        if isinstance(cmd, ICmd):
            if cmd.instruction == pat:
                logger.debug(f"\tmatching instr {pat}")
                self._record_match()
                return
        self._reset_match()

    def _match_any_zero_or_more(self) -> None:
        assert self._pat_idx > 0, "wildcard at start of pattern not allowed"
        assert (
            self._pat_idx + 1 < self._pat_len
        ), "wildcard at end of pattern not allowed"

        next_pat = self._pattern[self._pat_idx + 1]
        assert isinstance(next_pat, GenericInstr) or isinstance(
            next_pat, BranchLabel
        ), "wildcard directly after ANY_ZERO_OR_MORE not allowed"

        cmd = self._commands[self._cmd_idx]
        if isinstance(next_pat, BranchLabel):
            if isinstance(cmd, ICmd):
                logger.debug("\tmatching BranchLabel after * wildcard")
                self._pat_idx += 2
        elif isinstance(next_pat, GenericInstr):
            if isinstance(cmd, ICmd):
                if cmd.instruction == next_pat:
                    logger.debug(f"\tmatching instr {next_pat} after * wildcard")
                    self._pat_idx += 2
        else:
            assert False

    def match(self) -> bool:
        logger.debug(f"trying to match {self._pattern}")
        while True:
            if self._pat_idx == self._pat_len:
                return True

            if self._cmd_idx == len(self._commands):
                return False

            curr_pat = self._pattern[self._pat_idx]
            logger.debug(f"curr pat: {curr_pat}")

            if curr_pat == PatternWildcard.ANY_ONE:
                self._match_any_one()
            elif curr_pat == PatternWildcard.BRANCH_LABEL:
                self._match_branch_label()
            elif isinstance(curr_pat, GenericInstr):
                self._match_instr()
            elif curr_pat == PatternWildcard.ANY_ZERO_OR_MORE:
                self._match_any_zero_or_more()
            else:
                assert False

            self._cmd_idx += 1


class PreSubroutineInspector:
    def __init__(self, subroutine: PreSubroutine) -> None:
        self._subroutine = subroutine

    def contains_instr(self, instr_type: GenericInstr) -> bool:
        for cmd in self._subroutine.commands:
            cmd_instr_type = cmd.instruction if isinstance(cmd, ICmd) else None
            if cmd_instr_type == instr_type:
                return True
        return False

    def match_pattern(
        self, pattern: List[Union[GenericInstr, PatternWildcard]]
    ) -> bool:
        return PatternMatcher(self._subroutine.commands, pattern).match()


def test_simple():
    with DebugConnection("conn") as conn:
        q1 = Qubit(conn)
        q2 = Qubit(conn)
        q1.H()
        q2.X()
        q1.X()
        q2.H()

        subroutine = conn._builder._pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)
    assert inspector.contains_instr(GenericInstr.QALLOC)
    assert inspector.contains_instr(GenericInstr.SET)
    assert not inspector.contains_instr(GenericInstr.ROT_X)

    assert inspector.match_pattern(
        [
            GenericInstr.QALLOC,
            GenericInstr.INIT,
            GenericInstr.SET,
        ]
    )

    assert inspector.match_pattern(
        [
            GenericInstr.H,
            PatternWildcard.ANY_ONE,
            GenericInstr.X,
        ]
    )


def test_loop():
    with DebugConnection("conn") as conn:
        q = Qubit(conn)
        with conn.loop(2):
            q.H()

        subroutine = conn._builder._pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)
    assert inspector.contains_instr(GenericInstr.QALLOC)
    assert inspector.contains_instr(GenericInstr.SET)
    assert not inspector.contains_instr(GenericInstr.ROT_X)

    assert inspector.match_pattern(
        [
            PatternWildcard.BRANCH_LABEL,
            GenericInstr.BEQ,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.JMP,
            PatternWildcard.BRANCH_LABEL,
        ]
    )


def test_create_epr():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection("Alice", epr_sockets=[epr_socket]) as conn:
        epr = epr_socket.create()[0]

        epr.rot_Z(angle=math.pi)
        epr.H()

        _ = epr.measure(store_array=False)

        subroutine = conn._builder._pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)

    assert inspector.match_pattern(
        [
            GenericInstr.ARRAY,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.CREATE_EPR,
            GenericInstr.WAIT_ALL,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.ROT_Z,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.H,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.RET_ARR,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.RET_REG,
        ]
    )


if __name__ == "__main__":
    # set_log_level("DEBUG")
    # test_simple()
    # test_loop()
    test_create_epr()
