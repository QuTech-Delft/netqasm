import ctypes

from netqasm import encoding
from netqasm.instructions import Instruction, COMMAND_STRUCTS
from netqasm.subroutine import (
    Command,
    Register,
    Address,
    Subroutine,
    ArrayEntry,
    ArraySlice,
)

from netqasm.subroutine import Subroutine, Command
from netqasm.oop.instr import InstrMap
from netqasm.oop.vanilla import get_vanilla_map

from netqasm import subroutine

INSTR_ID = ctypes.c_uint8

class Deserializer:
    def __init__(self, instr_map: InstrMap):
        self.instr_map = instr_map

    def _parse_metadata(self, raw):
        metadata = raw[:encoding.METADATA_BYTES]
        metadata = encoding.Metadata.from_buffer_copy(metadata)
        data = raw[encoding.METADATA_BYTES:]
        return metadata, data

    def deserialize_subroutine(self, raw: bytes) -> Subroutine:
        metadata, raw = self._parse_metadata(raw)
        if (len(raw) % encoding.COMMAND_BYTES) != 0:
            raise ValueError("Length of data not a multiple of command length")
        num_commands = int(len(raw) / encoding.COMMAND_BYTES)
        commands = [
            self.deserialize_command(raw[i * encoding.COMMAND_BYTES:(i + 1) * encoding.COMMAND_BYTES])
            for i in range(num_commands)]
        return Subroutine(
            netqasm_version=tuple(metadata.netqasm_version),
            app_id=metadata.app_id,
            commands=commands,
        )

    def deserialize_command(self, raw: bytes) -> Command:
        # peek next byte to check instruction type
        instr_id = INSTR_ID.from_buffer_copy(raw[:1]).value
        instr_cls = self.instr_map.id_map[instr_id]
        instr = instr_cls.deserialize_from(raw)
        return instr


def parse_binary_subroutine(data: bytes) -> Subroutine:
    return Deserializer(instr_map=get_vanilla_map()).deserialize_subroutine(data)


def parse_metadata(data):
    metadata = data[:encoding.METADATA_BYTES]
    metadata = encoding.Metadata.from_buffer_copy(metadata)
    data = data[encoding.METADATA_BYTES:]
    return metadata, data


def parse_binary_command(data: bytes) -> subroutine.Command:
    instruction_id = encoding.INSTR_ID.from_buffer_copy(data[:1]).value
    instr = Instruction(instruction_id)
    command_struct = COMMAND_STRUCTS[instr].from_buffer_copy(data)
    command = _command_struct_to_command(command_struct)
    return command


def _command_struct_to_command(command: encoding.Command) -> subroutine.Command:
    instr = Instruction(command.id)
    field_values = [
        getattr(command, field_name)
        for field_name, _ in command._fields_
        if not field_name == encoding.PADDING_FIELD
    ]
    args = []
    operands = [_field_struct_to_arg_operand(field_value) for field_value in field_values]

    return Command(
        instruction=instr,
        args=args,
        operands=operands,
    )


def _field_struct_to_arg_operand(field_value):
    if isinstance(field_value, int):
        return field_value
    elif isinstance(field_value, encoding.Register):
        register_name = encoding.RegisterName(field_value.register_name)
        return Register(
            name=register_name,
            index=field_value.register_index,
        )
    elif isinstance(field_value, encoding.Address):
        return Address(address=field_value.address)
    elif isinstance(field_value, encoding.ArrayEntry):
        return ArrayEntry(
            address=_field_struct_to_arg_operand(field_value.address),
            index=_field_struct_to_arg_operand(field_value.index),
        )
    elif isinstance(field_value, encoding.ArraySlice):
        return ArraySlice(
            address=_field_struct_to_arg_operand(field_value.address),
            start=_field_struct_to_arg_operand(field_value.start),
            stop=_field_struct_to_arg_operand(field_value.stop),
        )
    else:
        raise TypeError(f"Unknown field_value {field_value} of type {type(field_value)}")
