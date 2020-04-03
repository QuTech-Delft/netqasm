from enum import Enum
from typing import List, Union
from dataclasses import dataclass

from netqasm.string_util import rspaces


@dataclass
class Constant:
    value: int

    def __str__(self):
        return str(self.value)


@dataclass
class Label:
    name: str

    def __str__(self):
        return self.name


class RegisterName(Enum):
    # Standard register
    R = "R"
    # Qubit addresses
    Q = "Q"
    # Measurment outcomes
    M = "M"
    # Entanglement information
    E = "E"


@dataclass
class Register:
    name: RegisterName
    value: int

    def __str__(self):
        return f"{self.name.value}{self.value}"


Value = Union[Constant, Register]


@dataclass
class MemoryAddress:
    base_address: Value
    index: Union[None, Value]

    def __str__(self):
        index = "" if self.index is None else f"{Symbols.INDEX_BRACKETS[0]}{self.index}{Symbols.INDEX_BRACKETS[1]}"
        return f"{self.base_address}{index}"


@dataclass
class Command:
    instruction: str
    args: List[Constant]
    operands: List[Union[Constant, Register, MemoryAddress, Label]]

    def __str__(self):
        if len(self.args) == 0:
            args = ''
        else:
            args = Symbols.ARGS_DELIM.join(str(arg) for arg in self.args)
            args = Symbols.ARGS_BRACKETS[0] + args + Symbols.ARGS_BRACKETS[1]
        operands = ' '.join(str(operand) for operand in self.operands)
        return f"{self.instruction}{args} {operands}"


@dataclass
class BranchLabel:
    name: str

    def __str__(self):
        return self.name + Symbols.BRANCH_END


@dataclass
class Subroutine:
    netqasm_version: str
    app_id: int
    commands: List[Union[Command, BranchLabel]]

    def __str__(self):
        to_return = f"Subroutine (netqasm_version={self.netqasm_version}, app_id={self.app_id}):\n"
        for i, command in enumerate(self.commands):
            to_return += f"{rspaces(i)} {command}\n"
        return to_return


class Symbols:
    COMMENT_START = '//'
    BRANCH_END = ':'
    MACRO_END = '!'
    ADDRESS_START = '@'
    ARGS_BRACKETS = '()'
    ARGS_DELIM = ','
    INDEX_BRACKETS = '[]'

    PREAMBLE_START = '#'
    PREAMBLE_NETQASM = 'NETQASM'
    PREAMBLE_APPID = 'APPID'
    PREAMBLE_DEFINE = 'DEFINE'
    PREAMBLE_DEFINE_BRACKETS = r'{}'
