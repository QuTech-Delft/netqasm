from enum import Enum
from typing import List, Union
from dataclasses import dataclass

from netqasm import encoding
from netqasm.util import NetQASMInstrError
from netqasm.encoding import RegisterName
from netqasm.string_util import rspaces
from netqasm.instructions import string_to_instruction, COMMAND_STRUCTS


@dataclass
class Constant:
    value: int

    def __str__(self):
        return str(self.value)

    @property
    def cstruct(self):
        return encoding.Value.from_buffer_copy(bytes(encoding.Constant(self.value)))

    def __bytes__(self):
        return bytes(self.cstruct)


@dataclass
class Label:
    name: str

    def __str__(self):
        return self.name


@dataclass
class Register:
    name: RegisterName
    value: int

    def __str__(self):
        return f"{self.name.name}{self.value}"

    @property
    def cstruct(self):
        return encoding.Value.from_buffer_copy(bytes(encoding.Register(self.name.value, self.value)))

    def __bytes__(self):
        return bytes(self.cstruct)


Value = Union[Constant, Register]


@dataclass
class Address:
    base_address: Value
    index: Union[None, Value]

    def __str__(self):
        index = "" if self.index is None else f"{Symbols.INDEX_BRACKETS[0]}{self.index}{Symbols.INDEX_BRACKETS[1]}"
        return f"{Symbols.ADDRESS_START}{self.base_address}{index}"

    @property
    def cstruct(self):
        if self.index is None:
            return encoding.Address(
                read_index=False,
                address=self.base_address.cstruct,
            )
        else:
            return encoding.Address(
                read_index=True,
                address=self.base_address.cstruct,
                index=self.index.cstruct,
            )

    def __bytes__(self):
        return bytes(self.cstruct)


@dataclass
class Command:
    instruction: str
    args: List[Constant]
    operands: List[Union[Constant, Register, Address, Label]]

    def __str__(self):
        if len(self.args) == 0:
            args = ''
        else:
            args = Symbols.ARGS_DELIM.join(str(arg) for arg in self.args)
            args = Symbols.ARGS_BRACKETS[0] + args + Symbols.ARGS_BRACKETS[1]
        operands = ' '.join(str(operand) for operand in self.operands)
        return f"{self.instruction}{args} {operands}"

    @property
    def cstruct(self):
        instr = string_to_instruction(self.instruction)
        command = COMMAND_STRUCTS[instr]
        args = [arg.cstruct for arg in self.args]
        # if self.instruction == "array":
        #     x1 = self.args[0]
        #     x2 = x1.cstruct
        #     x3 = bytes(x2)
        #     x4 = encoding.Value.from_buffer_copy(x3)
        #     x5 = x4.to_tp()
        #     x6 = bytes(x5)
        #     print(x1)
        #     print(x2)
        #     print(x3)
        #     print(x4)
        #     print(x5)
        #     print(x6)
        #     breakpoint()
        operands = [op.cstruct for op in self.operands]
        fields = args + operands
        if not len(fields) != len(command._fields_):
            raise NetQASMInstrError("Unexpected number of fields for command {command}, expected {len(command._fields_)}, got {len(fields)}")
        return command(*fields)

    def __bytes__(self):
        return bytes(self.cstruct)


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


    def __len__(self):
        return len(self.commands)

    @property
    def cstructs(self):
        return [command.cstruct for command in self.commands]

    def __bytes__(self):
        return b''.join(bytes(command) for command in self.commands)


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
