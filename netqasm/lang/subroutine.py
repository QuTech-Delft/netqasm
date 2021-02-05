from typing import List, Union, Optional
from dataclasses import dataclass

from netqasm.lang import encoding
from netqasm.util.string import rspaces
from netqasm.lang.instr.instr_enum import Instruction, instruction_to_string
from netqasm.lang.symbols import Symbols

from netqasm.lang.instr.base import NetQASMInstruction, DebugInstruction
from netqasm.lang.instr.operand import (
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
    args: List[int] = None  # type: ignore
    operands: List[_OPERAND_UNION] = None  # type: ignore
    lineno: Optional[int] = None

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
    lineno: Optional[int] = None

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
    commands: List[Union[Command, BranchLabel]]

    def __str__(self):
        to_return = f"PreSubroutine (netqasm_version={self.netqasm_version}, app_id={self.app_id}):\n"
        to_return += " LN | HLN | CMD\n"
        for i, command in enumerate(self.commands):
            to_return += f"{rspaces(i)} {command.debug_str}\n"
        return to_return


@dataclass
class Subroutine:
    """
    A :class:`~.Subroutine` object represents a subroutine consisting of valid
    instructions, i.e. objects deriving from :class:`~.NetQASMInstruction`.

    :class:`~.Subroutine` s are executed by :class:`~.Executioner` s.
    """
    netqasm_version: tuple
    app_id: int
    commands: List[NetQASMInstruction]

    def __str__(self):
        to_return = f"Subroutine (netqasm_version={self.netqasm_version}, app_id={self.app_id}):\n"
        to_return += " LN | HLN | CMD\n"
        for i, command in enumerate(self.commands):
            if isinstance(command, DebugInstruction):
                to_return += f"# {command.text}\n"
            else:
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
