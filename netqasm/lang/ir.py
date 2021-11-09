from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, List, Optional, Union

from netqasm.lang.symbols import Symbols
from netqasm.util.string import rspaces

if TYPE_CHECKING:
    from netqasm.util import log

from netqasm.lang.operand import Address, ArrayEntry, ArraySlice, Label, Register


class GenericInstr(Enum):
    # Allocation
    QALLOC = auto()
    # Initialization
    INIT = auto()
    ARRAY = auto()
    SET = auto()
    # Memory
    STORE = auto()
    LOAD = auto()
    UNDEF = auto()
    LEA = auto()
    # Classical logic
    JMP = auto()
    BEZ = auto()
    BNZ = auto()
    BEQ = auto()
    BNE = auto()
    BLT = auto()
    BGE = auto()
    # Classical operations
    ADD = auto()
    SUB = auto()
    ADDM = auto()
    SUBM = auto()
    # Single-qubit gates
    X = auto()
    Y = auto()
    Z = auto()
    H = auto()
    S = auto()
    K = auto()
    T = auto()
    # Single-qubit rotations
    ROT_X = auto()
    ROT_Y = auto()
    ROT_Z = auto()
    # Two-qubit gates
    CNOT = auto()
    CPHASE = auto()
    # Measurement
    MEAS = auto()
    # Entanglement generation
    CREATE_EPR = auto()
    RECV_EPR = auto()
    # Waiting
    WAIT_ALL = auto()
    WAIT_ANY = auto()
    WAIT_SINGLE = auto()
    # Deallocation
    QFREE = auto()
    # Return
    RET_REG = auto()
    RET_ARR = auto()

    CROT_X = auto()
    CROT_Y = auto()
    CROT_Z = auto()

    # Move source qubit to target qubit (target is overwritten)
    MOV = auto()

    # Breakpoint
    BREAKPOINT = auto()


class BreakpointAction(Enum):
    NOP = 0
    DUMP_LOCAL_STATE = 1
    DUMP_GLOBAL_STATE = 2


class BreakpointRole(Enum):
    CREATE = 0
    RECEIVE = 1


def instruction_to_string(instr):
    if not isinstance(instr, GenericInstr):
        raise ValueError(f"Unknown instruction {instr}")
    return instr.name.lower()


def flip_branch_instr(instr: GenericInstr) -> GenericInstr:
    try:
        return {
            GenericInstr.BEQ: GenericInstr.BNE,
            GenericInstr.BNE: GenericInstr.BEQ,
            GenericInstr.BLT: GenericInstr.BGE,
            GenericInstr.BGE: GenericInstr.BLT,
            GenericInstr.BEZ: GenericInstr.BNZ,
            GenericInstr.BNZ: GenericInstr.BEZ,
        }[instr]
    except KeyError:
        raise ValueError(f"Not a branch instruction {instr}")


_STRING_TO_INSTRUCTION = {instruction_to_string(instr): instr for instr in GenericInstr}


def string_to_instruction(instr_str):
    instr = _STRING_TO_INSTRUCTION.get(instr_str)
    if instr is None:
        raise ValueError(f"Unknown instruction {instr_str}")
    return instr


T_OperandUnion = Union[
    int,
    Register,
    Address,
    ArrayEntry,
    ArraySlice,
    Label,
]


def _get_lineo_str(lineno):
    if lineno is None:
        lineno = "()"
    else:
        lineno = f"({lineno})"
    return f"{rspaces(lineno, min_chars=5)} "


@dataclass
class ICmd:
    instruction: GenericInstr
    args: List[int] = None  # type: ignore
    operands: List[T_OperandUnion] = None  # type: ignore
    lineno: Optional[log.HostLine] = None

    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.operands is None:
            self.operands = []

    def __str__(self):
        return self._build_str(show_lineno=False)

    @property
    def debug_str(self):
        return self._build_str(show_lineno=True)

    def _build_str(self, show_lineno=False):
        if len(self.args) == 0:
            args = ""
        else:
            args = Symbols.ARGS_DELIM.join(str(arg) for arg in self.args)
            args = Symbols.ARGS_BRACKETS[0] + args + Symbols.ARGS_BRACKETS[1]
        operands = " ".join(str(operand) for operand in self.operands)
        instr_name = instruction_to_string(self.instruction)
        if show_lineno:
            lineno_str = _get_lineo_str(self.lineno)
        else:
            lineno_str = ""
        return f"{lineno_str}{instr_name}{args} {operands}"


@dataclass
class BranchLabel:
    name: str
    lineno: Optional[log.HostLine] = None

    def _assert_types(self):
        assert isinstance(self.name, str)

    def __str__(self):
        return self._build_str(show_lineno=False)

    @property
    def debug_str(self):
        return self._build_str(show_lineno=True)

    def _build_str(self, show_lineno=False):
        if show_lineno:
            lineno_str = _get_lineo_str(self.lineno)
        else:
            lineno_str = ""
        return f"{lineno_str}{self.name}{Symbols.BRANCH_END}"


@dataclass
class PreSubroutine:
    """
    A :class:`~.PreSubroutine` object represents a preliminary subroutine that consists of
    general 'commands' that might not yet be valid NetQASM instructions.
    These commands can include labels, or instructions with immediates that still need
    to be converted to registers.

    :class:`~.PreSubroutine`s are currently only used by the sdk and the text parser (netqasm.parser.text).
    In both cases they are converted into :class:`~.Subroutine` objects before given to other package components.
    """

    netqasm_version: tuple
    app_id: int
    commands: List[Union[ICmd, BranchLabel]]

    def __str__(self):
        to_return = f"PreSubroutine (netqasm_version={self.netqasm_version}, app_id={self.app_id}):\n"
        to_return += " LN | HLN | CMD\n"
        for i, command in enumerate(self.commands):
            to_return += f"{rspaces(i)} {command.debug_str}\n"
        return to_return
