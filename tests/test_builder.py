import math
from enum import Enum, auto
from typing import List, Optional, Union

from netqasm.lang.ir import BranchLabel, GenericInstr, ICmd, PreSubroutine
from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk.build_types import NVHardwareConfig
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.constraint import ValueAtMostConstraint
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.futures import RegFuture
from netqasm.sdk.qubit import Qubit

logger = get_netqasm_logger()


class PatternWildcard(Enum):
    ANY_ONE = auto()
    ANY_ZERO_OR_MORE = auto()
    BRANCH_LABEL = auto()


class PatternMatcher:
    def __init__(
        self,
        commands: List[Union[ICmd, BranchLabel]],
        pattern: List[Union[GenericInstr, PatternWildcard]],
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
        assert (
            isinstance(next_pat, GenericInstr)
            or next_pat == PatternWildcard.BRANCH_LABEL
        ), "wildcard directly after ANY_ZERO_OR_MORE not allowed"

        cmd = self._commands[self._cmd_idx]
        if next_pat == PatternWildcard.BRANCH_LABEL:
            if isinstance(cmd, BranchLabel):
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

        subroutine = conn.builder.subrt_pop_pending_subroutine()
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

        subroutine = conn.builder.subrt_pop_pending_subroutine()
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


def test_branching():
    with DebugConnection("Alice") as conn:

        def if_true(conn):
            q = Qubit(conn)
            _ = q.measure()

        conn.if_eq(42, 42, if_true)

        q2 = Qubit(conn)
        m2 = q2.measure()
        with m2.if_ne(0):
            _ = Qubit(conn)

        with m2.if_ez():
            _ = Qubit(conn)

        subroutine = conn.builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)

    assert inspector.match_pattern(
        [
            GenericInstr.BNE,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,
        ]
    )

    assert inspector.match_pattern(
        [
            GenericInstr.MEAS,
            GenericInstr.QFREE,
            GenericInstr.STORE,
            GenericInstr.LOAD,
            GenericInstr.BEQ,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,
        ]
    )


def test_loop_context():
    with DebugConnection("conn") as conn:
        q = Qubit(conn)
        with conn.loop(2):
            q.H()

        subroutine = conn.builder.subrt_pop_pending_subroutine()
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


def test_looping():
    with DebugConnection("Alice") as conn:

        def body(conn: DebugConnection, reg: RegFuture):
            q = Qubit(conn)
            _ = q.measure()

        conn.loop_body(body, 42, loop_register="C9")

        subroutine = conn.builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)

    assert inspector.match_pattern(
        [
            GenericInstr.SET,
            PatternWildcard.BRANCH_LABEL,
            GenericInstr.BEQ,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.ADD,
            GenericInstr.JMP,
            PatternWildcard.BRANCH_LABEL,
        ]
    )


def test_futures():
    with DebugConnection("Alice") as conn:

        q = Qubit(conn)
        m = q.measure()
        with m.if_ne(0):
            _ = Qubit(conn)
        with m.if_ez():
            _ = Qubit(conn)

        subroutine = conn.builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)

    assert inspector.match_pattern(
        [
            GenericInstr.MEAS,
            GenericInstr.QFREE,
            GenericInstr.STORE,
            GenericInstr.LOAD,
            GenericInstr.BEQ,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,
            GenericInstr.LOAD,
            GenericInstr.BNZ,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,
        ]
    )


def test_nested():
    with DebugConnection("Alice") as conn:

        q = Qubit(conn)
        m = q.measure()
        with m.if_eq(0):
            with m.if_eq(1):
                _ = Qubit(conn)

        with conn.loop(2):
            with conn.loop(3):
                _ = Qubit(conn)

        with conn.loop(2):
            with m.if_eq(0):
                _ = Qubit(conn)

        with m.if_eq(0):
            with conn.loop(2):
                _ = Qubit(conn)

        subroutine = conn.builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)

    assert inspector.match_pattern(
        [
            GenericInstr.BNE,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.BNE,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,  # IF_EXIT
            PatternWildcard.BRANCH_LABEL,  # IF_EXIT1
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,  # LOOP1
            GenericInstr.BEQ,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,  # LOOP
            GenericInstr.BEQ,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.JMP,
            PatternWildcard.BRANCH_LABEL,  # LOOP_EXIT
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.JMP,
            PatternWildcard.BRANCH_LABEL,  # LOOP_EXIT1
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,  # LOOP2
            GenericInstr.BEQ,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.BNE,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,  # IF_EXIT2
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.JMP,
            PatternWildcard.BRANCH_LABEL,  # LOOP_EXIT2
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.BNE,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,  # LOOP3
            GenericInstr.BEQ,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.JMP,
            PatternWildcard.BRANCH_LABEL,  # LOOP_EXIT3
            PatternWildcard.BRANCH_LABEL,  # IF_EXIT3
        ]
    )


def test_epr_keep_info():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection("Alice", epr_sockets=[epr_socket]) as conn:
        eprs, infos = epr_socket.create_keep_with_info()
        epr, info = eprs[0], infos[0]

        _ = epr.measure(store_array=False)
        with info.generation_duration.if_ge(1337):
            _ = Qubit(conn)

        subroutine = conn._builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)
    assert inspector.match_pattern(
        [
            GenericInstr.CREATE_EPR,
            GenericInstr.WAIT_ALL,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.LOAD,
            GenericInstr.BLT,
            GenericInstr.SET,
            GenericInstr.QALLOC,
            GenericInstr.INIT,
            PatternWildcard.BRANCH_LABEL,
        ]
    )


def test_epr_context():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection("Alice", epr_sockets=[epr_socket]) as conn:

        with epr_socket.create_context(5) as (qubit, index):
            with index.if_eq(1337):
                qubit.H()
            _ = qubit.measure()

        subroutine = conn._builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)
    assert inspector.match_pattern(
        [
            GenericInstr.CREATE_EPR,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.WAIT_ALL,
            GenericInstr.BNE,
            GenericInstr.LOAD,
            GenericInstr.H,
            PatternWildcard.BRANCH_LABEL,
            GenericInstr.LOAD,
            GenericInstr.MEAS,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,
        ]
    )


def test_epr_context_future_index():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection("Alice", epr_sockets=[epr_socket]) as conn:
        outcomes = conn.new_array(5)

        with epr_socket.create_context(5) as (qubit, index):
            outcome = outcomes.get_future_index(index)
            qubit.measure(outcome)

        subroutine = conn._builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)
    assert inspector.match_pattern(
        [
            GenericInstr.CREATE_EPR,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.WAIT_ALL,
            GenericInstr.LOAD,
            GenericInstr.MEAS,
            GenericInstr.QFREE,
            GenericInstr.STORE,
            GenericInstr.ADD,
            GenericInstr.JMP,
            PatternWildcard.BRANCH_LABEL,
        ]
    )


def test_epr_post():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection("Alice", epr_sockets=[epr_socket]) as conn:
        outcomes = conn.new_array(10)

        def post_create(_: DebugConnection, q: Qubit, index: RegFuture):
            q.H()
            index.add(1)
            outcome = outcomes.get_future_index(index)
            q.measure(outcome)

        epr_socket.create_keep(number=10, post_routine=post_create, sequential=True)

        subroutine = conn._builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)
    assert inspector.match_pattern(
        [
            GenericInstr.CREATE_EPR,
            PatternWildcard.ANY_ZERO_OR_MORE,
            PatternWildcard.BRANCH_LABEL,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.WAIT_ALL,
            GenericInstr.LOAD,
            GenericInstr.H,
            GenericInstr.ADD,
            GenericInstr.LOAD,
            GenericInstr.MEAS,
            GenericInstr.QFREE,
            GenericInstr.STORE,
            GenericInstr.ADD,
            GenericInstr.JMP,
            PatternWildcard.BRANCH_LABEL,
        ]
    )


def test_try():
    with DebugConnection("Alice") as conn:

        with conn.try_until_success(max_tries=1):
            q = Qubit(conn)
            q.measure()

        subroutine = conn.builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)
    assert inspector.match_pattern(
        [
            GenericInstr.QALLOC,
            GenericInstr.INIT,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.MEAS,
            GenericInstr.QFREE,
            GenericInstr.STORE,
        ]
    )


def test_loop_until():
    with DebugConnection("Alice") as conn:

        with conn.loop_until(max_iterations=10) as loop:
            q = Qubit(conn)
            m = q.measure()
            constraint = ValueAtMostConstraint(m, 42)
            loop.set_exit_condition(constraint)

        subroutine = conn.builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)
    assert inspector.match_pattern(
        [
            PatternWildcard.BRANCH_LABEL,
            GenericInstr.BEQ,
            GenericInstr.SET,
            GenericInstr.QALLOC,
            GenericInstr.INIT,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.MEAS,
            GenericInstr.QFREE,
            GenericInstr.STORE,
            GenericInstr.LOAD,
            GenericInstr.BLT,
            GenericInstr.ADD,
            GenericInstr.JMP,
            PatternWildcard.BRANCH_LABEL,
        ]
    )


def test_epr_min_fidelity_all():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection("Alice", epr_sockets=[epr_socket]) as conn:
        epr_socket.create_keep(number=2, min_fidelity_all_at_end=80, max_tries=100)

        subroutine = conn._builder.subrt_pop_pending_subroutine()
        print(subroutine)

    inspector = PreSubroutineInspector(subroutine)
    assert inspector.match_pattern(
        [
            GenericInstr.SET,
            PatternWildcard.BRANCH_LABEL,
            GenericInstr.BEQ,
            GenericInstr.CREATE_EPR,
            GenericInstr.WAIT_ALL,
            GenericInstr.LOAD,
            GenericInstr.BLT,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.UNDEF,
            PatternWildcard.ANY_ZERO_OR_MORE,
            GenericInstr.JMP,
            PatternWildcard.BRANCH_LABEL,
        ]
    )


def test_create_multiple_eprs():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection("Alice", epr_sockets=[epr_socket]) as conn:
        epr0, epr1 = epr_socket.create(2)

        epr0.X()
        epr1.Y()

        _ = epr0.measure(store_array=False)
        _ = epr1.measure(store_array=False)

        subroutine = conn.builder.subrt_pop_pending_subroutine()
        print(subroutine)

    # Check if the qubits have the correct ID
    epr0_id = 0
    epr1_id = 1

    for i, cmd in enumerate(subroutine.commands):
        if not isinstance(cmd, ICmd):
            continue
        if cmd.instruction == GenericInstr.X:
            prev_set_instr = subroutine.commands[i - 1]
            assert prev_set_instr.operands[1] == epr0_id
        elif cmd.instruction == GenericInstr.Y:
            prev_set_instr = subroutine.commands[i - 1]
            assert prev_set_instr.operands[1] == epr1_id


def test_create_2_eprs_NV():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection(
        "Alice",
        epr_sockets=[epr_socket],
        hardware_config=NVHardwareConfig(2),
    ) as conn:
        epr0, epr1 = epr_socket.create_keep(2)
        print(f"epr0 ID: {epr0.qubit_id}")
        print(f"epr1 ID: {epr1.qubit_id}")

        epr0.X()
        epr1.Y()

        _ = epr0.measure(store_array=False)
        _ = epr1.measure(store_array=False)

        subroutine = conn.builder.subrt_pop_pending_subroutine()
        print(subroutine)

    # Check if the qubits have the correct ID
    epr0_id = 1
    epr1_id = 0

    for i, cmd in enumerate(subroutine.commands):
        if not isinstance(cmd, ICmd):
            continue
        if cmd.instruction == GenericInstr.X:
            prev_set_instr = subroutine.commands[i - 1]
            assert prev_set_instr.operands[1] == epr0_id
        elif cmd.instruction == GenericInstr.Y:
            prev_set_instr = subroutine.commands[i - 1]
            assert prev_set_instr.operands[1] == epr1_id


def test_create_3_eprs_NV():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection(
        "Alice",
        epr_sockets=[epr_socket],
        hardware_config=NVHardwareConfig(3),
    ) as conn:
        epr0, epr1, epr2 = epr_socket.create_keep(3)
        print(f"epr0 ID: {epr0.qubit_id}")
        print(f"epr1 ID: {epr1.qubit_id}")
        print(f"epr2 ID: {epr2.qubit_id}")

        epr0.X()
        epr1.Y()
        epr2.Z()

        _ = epr0.measure(store_array=False)
        _ = epr1.measure(store_array=False)
        _ = epr2.measure(store_array=False)

        subroutine = conn.builder.subrt_pop_pending_subroutine()
        print(subroutine)

    # Check if the qubits have the correct ID
    epr0_id = 2
    epr1_id = 1
    epr2_id = 0

    for i, cmd in enumerate(subroutine.commands):
        if not isinstance(cmd, ICmd):
            continue
        if cmd.instruction == GenericInstr.X:
            prev_set_instr = subroutine.commands[i - 1]
            assert prev_set_instr.operands[1] == epr0_id
        elif cmd.instruction == GenericInstr.Y:
            prev_set_instr = subroutine.commands[i - 1]
            assert prev_set_instr.operands[1] == epr1_id
        elif cmd.instruction == GenericInstr.Z:
            prev_set_instr = subroutine.commands[i - 1]
            assert prev_set_instr.operands[1] == epr2_id


def test_bqc_receiver_NV():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection(
        "Alice",
        epr_sockets=[epr_socket],
        hardware_config=NVHardwareConfig(2),
        compiler=NVSubroutineCompiler,
    ) as conn:
        carbon, electron = epr_socket.recv_keep(2)

        electron.cphase(carbon)

        delta1 = math.pi
        electron.rot_Z(angle=delta1)
        electron.H()
        _ = electron.measure(store_array=False)

        delta2 = math.pi
        carbon.rot_Z(angle=delta2)
        carbon.H()
        _ = carbon.measure()

        presubroutine = conn.builder.subrt_pop_pending_subroutine()
        print(presubroutine)
        compiled_subroutine = conn.builder.subrt_compile_subroutine(presubroutine)
        print(compiled_subroutine)


def test_bqc_receiver_NV_min_fidelity():
    DebugConnection.node_ids = {
        "Alice": 0,
        "Bob": 1,
    }

    epr_socket = EPRSocket("Bob")

    with DebugConnection(
        "Alice",
        epr_sockets=[epr_socket],
        hardware_config=NVHardwareConfig(2),
        compiler=NVSubroutineCompiler,
    ) as conn:
        carbon, electron = epr_socket.recv_keep(
            2, min_fidelity_all_at_end=80, max_tries=25
        )

        electron.cphase(carbon)

        delta1 = math.pi
        electron.rot_Z(angle=delta1)
        electron.H()
        _ = electron.measure(store_array=False)

        delta2 = math.pi
        carbon.rot_Z(angle=delta2)
        carbon.H()
        _ = carbon.measure()

        presubroutine = conn.builder.subrt_pop_pending_subroutine()
        print(presubroutine)
        compiled_subroutine = conn.builder.subrt_compile_subroutine(presubroutine)
        print(compiled_subroutine)


if __name__ == "__main__":
    # set_log_level("DEBUG")
    test_simple()
    test_create_epr()
    test_branching()
    test_loop_context()
    test_looping()
    test_futures()
    test_nested()
    test_epr_keep_info()
    test_epr_context()
    test_epr_context_future_index()
    test_epr_post()
    test_try()
    test_loop_until()
    test_epr_min_fidelity_all()
    test_create_multiple_eprs()
    test_create_2_eprs_NV()
    test_create_3_eprs_NV()
    test_bqc_receiver_NV()
    test_bqc_receiver_NV_min_fidelity()
