from __future__ import annotations
from typing import List, Union, Optional
from typing import TYPE_CHECKING
from dataclasses import dataclass

from netqasm.lang.instr.instr_enum import GenericInstr, instruction_to_string
from netqasm.util.string import rspaces
from netqasm.lang.symbols import Symbols

if TYPE_CHECKING:
    from netqasm.util.log import HostLine

from netqasm.lang.instr.operand import (
    Register,
    Address,
    ArrayEntry,
    ArraySlice,
    Label
)

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
