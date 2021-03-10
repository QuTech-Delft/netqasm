from __future__ import annotations
from typing import List, Union, Optional
from typing import TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

from netqasm.util.string import rspaces
from netqasm.lang.symbols import Symbols

if TYPE_CHECKING:
    from netqasm.util.log import HostLine

from netqasm.lang.operand import (
    Register,
    Address,
    ArrayEntry,
    ArraySlice,
    Label
)


class GenericInstr(Enum):
    # Allocation
    QALLOC = 1
    # Initialization
    INIT = 2
    ARRAY = 3
    SET = 4
    # Memory
    STORE = 5
    LOAD = 6
    UNDEF = 7
    LEA = 8
    # Classical logic
    JMP = 9
    BEZ = 10
    BNZ = 11
    BEQ = 12
    BNE = 13
    BLT = 14
    BGE = 15
    # Classical operations
    ADD = 16
    SUB = 17
    ADDM = 18
    SUBM = 19
    # Single-qubit gates
    X = 20
    Y = 21
    Z = 22
    H = 23
    S = 24
    K = 25
    T = 26
    # Single-qubit rotations
    ROT_X = 27
    ROT_Y = 28
    ROT_Z = 29
    # Two-qubit gates
    CNOT = 30
    CPHASE = 31
    # Measurement
    MEAS = 32
    # Entanglement generation
    CREATE_EPR = 33
    RECV_EPR = 34
    # Waiting
    WAIT_ALL = 35
    WAIT_ANY = 36
    WAIT_SINGLE = 37
    # Deallocation
    QFREE = 38
    # Return
    RET_REG = 39
    RET_ARR = 40

    # Move source qubit to target qubit (target is overwritten)
    MOV = 41

    CROT_X = 51
    CROT_Y = 52


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
    lineno: Optional[HostLine] = None

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
            args = ''
        else:
            args = Symbols.ARGS_DELIM.join(str(arg) for arg in self.args)
            args = Symbols.ARGS_BRACKETS[0] + args + Symbols.ARGS_BRACKETS[1]
        operands = ' '.join(str(operand) for operand in self.operands)
        instr_name = instruction_to_string(self.instruction)
        if show_lineno:
            lineno_str = _get_lineo_str(self.lineno)
        else:
            lineno_str = ""
        return f"{lineno_str}{instr_name}{args} {operands}"


@dataclass
class BranchLabel:
    name: str
    lineno: Optional[HostLine] = None

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
