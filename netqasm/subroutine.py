from typing import List, Union
from dataclasses import dataclass

from netqasm import encoding
from netqasm.string_util import rspaces
from netqasm.instructions import Instruction
from netqasm.symbols import Symbols

from netqasm.instr2.core import NetQASMInstruction
from netqasm.instr2.operand import (
    Register,
    Address,
    ArrayEntry,
    ArraySlice,
    Label
)


_OPERAND_UNION = Union[
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
class Command:
    instruction: Instruction
    args: List[int] = None
    operands: List[_OPERAND_UNION] = None
    lineno: int = None

    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.operands is None:
            self.operands = []


@dataclass
class BranchLabel:
    name: str
    lineno: int = None

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
    netqasm_version: tuple
    app_id: int
    commands: List[Union[Command, BranchLabel]]


@dataclass
class Subroutine:
    netqasm_version: tuple
    app_id: int
    commands: List[NetQASMInstruction]

    def __str__(self):
        to_return = f"Subroutine (netqasm_version={self.netqasm_version}, app_id={self.app_id}):\n"
        to_return += " LN | HLN | CMD\n"
        for i, command in enumerate(self.commands):
            to_return += f"{rspaces(i)} {command.debug_str}\n"
        return to_return

    def __len__(self):
        return len(self.commands)

    @property
    def cstructs(self):
        metadata = encoding.Metadata(
            netqasm_version=self.netqasm_version,
            app_id=self.app_id,
        )
        return [metadata] + [command.serialize() for command in self.commands]

    def __bytes__(self):
        return b''.join(bytes(cstruct) for cstruct in self.cstructs)
