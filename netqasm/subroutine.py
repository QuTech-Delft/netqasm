from typing import List, Union
from dataclasses import dataclass

from netqasm import encoding
from netqasm.util import NetQASMInstrError
from netqasm.encoding import RegisterName
from netqasm.string_util import rspaces
from netqasm.instructions import Instruction, COMMAND_STRUCTS, instruction_to_string


@dataclass
class Constant:
    value: int

    def _assert_types(self):
        assert isinstance(self.value, int)

    def __str__(self):
        return str(self.value)

    @property
    def cstruct(self):
        self._assert_types()
        return encoding.CONSTANT(self.value)

    def __bytes__(self):
        return bytes(self.cstruct)


@dataclass
class Label:
    name: str

    def _assert_types(self):
        assert isinstance(self.name, str)

    def __str__(self):
        return self.name


@dataclass
class Register:
    name: RegisterName
    index: int

    def _assert_types(self):
        assert isinstance(self.name, RegisterName)
        assert isinstance(self.index, int)

    def __str__(self):
        return f"{self.name.name}{self.index}"

    @property
    def cstruct(self):
        self._assert_types()
        return encoding.Register(self.name.value, self.index)

    def __bytes__(self):
        return bytes(self.cstruct)


Value = Union[Constant, Register]


@dataclass
class Address:
    address: Constant

    def __post_init__(self):
        if isinstance(self.address, int):
            self.address = Constant(self.address)

    def _assert_types(self):
        assert isinstance(self.address, Constant)

    def __str__(self):
        return f"{Symbols.ADDRESS_START}{self.address}"

    @property
    def cstruct(self):
        self._assert_types()
        return encoding.Address(self.address.value)

    def __bytes__(self):
        return bytes(self.cstruct)


@dataclass
class ArrayEntry:
    address: Address
    index: Register

    def __post_init__(self):
        if isinstance(self.address, int):
            self.address = Address(Constant(self.address))

    def _assert_types(self):
        try:
            assert isinstance(self.address, Address)
            assert isinstance(self.index, Register)
        except Exception as err:
            breakpoint()
            raise err

    def __str__(self):
        index = f"{Symbols.INDEX_BRACKETS[0]}{self.index}{Symbols.INDEX_BRACKETS[1]}"
        return f"{self.address}{index}"

    @property
    def cstruct(self):
        self._assert_types()
        return encoding.ArrayEntry(
            self.address.cstruct,
            self.index.cstruct,
        )

    def __bytes__(self):
        return bytes(self.cstruct)


@dataclass
class ArraySlice:
    address: Address
    start: Register
    stop: Register

    def __post_init__(self):
        if isinstance(self.address, int):
            self.address = Address(Constant(self.address))

    def _assert_types(self):
        assert isinstance(self.address, Address)
        assert isinstance(self.start, Register)
        assert isinstance(self.stop, Register)

    def __str__(self):
        index = f"{Symbols.INDEX_BRACKETS[0]}{self.start}{Symbols.SLICE_DELIM}{self.stop}{Symbols.INDEX_BRACKETS[1]}"
        return f"{self.address}{index}"

    @property
    def cstruct(self):
        self._assert_types()
        return encoding.ArraySlice(
            self.address.cstruct,
            self.start.cstruct,
            self.stop.cstruct,
        )

    def __bytes__(self):
        return bytes(self.cstruct)


_OPERAND_UNION = Union[
    Constant,
    Register,
    Address,
    ArrayEntry,
    ArraySlice,
    Label,
]


@dataclass
class Command:
    instruction: Instruction
    args: List[Constant] = None
    operands: List[_OPERAND_UNION] = None

    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.operands is None:
            self.operands = []

    def _assert_types(self):
        assert isinstance(self.instruction, Instruction)
        assert all(isinstance(arg, _OPERAND_UNION.__args__) for arg in self.args)
        assert all(isinstance(operand, _OPERAND_UNION.__args__) for operand in self.operands)

    def __str__(self):
        if len(self.args) == 0:
            args = ''
        else:
            args = Symbols.ARGS_DELIM.join(str(arg) for arg in self.args)
            args = Symbols.ARGS_BRACKETS[0] + args + Symbols.ARGS_BRACKETS[1]
        operands = ' '.join(str(operand) for operand in self.operands)
        instr_name = instruction_to_string(self.instruction)
        return f"{instr_name}{args} {operands}"

    @property
    def cstruct(self):
        self._assert_types()
        command = COMMAND_STRUCTS[self.instruction]
        args = [arg.cstruct for arg in self.args]
        operands = [op.cstruct for op in self.operands]
        fields = args + operands
        if not len(fields) != len(command._fields_):
            raise NetQASMInstrError(f"Unexpected number of fields for command {command}, "
                                    f"expected {len(command._fields_)}, got {len(fields)}")
        return command(*fields)

    def __bytes__(self):
        return bytes(self.cstruct)


@dataclass
class BranchLabel:
    name: str

    def _assert_types(self):
        assert isinstance(self.name, str)

    def __str__(self):
        return self.name + Symbols.BRANCH_END


_COMMAND_UNION = Union[
    Command,
    BranchLabel,
]


@dataclass
class Subroutine:
    netqasm_version: tuple
    app_id: int
    commands: List[_COMMAND_UNION]

    def _assert_types(self):
        assert isinstance(self.netqasm_version, tuple)
        assert len(self.netqasm_version) == 2
        assert isinstance(self.app_id, int)
        assert all(isinstance(command, _COMMAND_UNION.__args__) for command in self.commands)

    def __str__(self):
        to_return = f"Subroutine (netqasm_version={self.netqasm_version}, app_id={self.app_id}):\n"
        for i, command in enumerate(self.commands):
            to_return += f"{rspaces(i)} {command}\n"
        return to_return

    def __len__(self):
        return len(self.commands)

    @property
    def cstructs(self):
        self._assert_types()
        metadata = encoding.Metadata(
            netqasm_version=self.netqasm_version,
            app_id=self.app_id,
        )
        return [metadata] + [command.cstruct for command in self.commands]

    def __bytes__(self):
        return b''.join(bytes(cstruct) for cstruct in self.cstructs)


class Symbols:
    COMMENT_START = '//'
    BRANCH_END = ':'
    MACRO_END = '!'
    ADDRESS_START = '@'
    ARGS_BRACKETS = '()'
    ARGS_DELIM = ','
    INDEX_BRACKETS = '[]'
    SLICE_DELIM = ':'

    PREAMBLE_START = '#'
    PREAMBLE_NETQASM = 'NETQASM'
    PREAMBLE_APPID = 'APPID'
    PREAMBLE_DEFINE = 'DEFINE'
    PREAMBLE_DEFINE_BRACKETS = r'{}'
