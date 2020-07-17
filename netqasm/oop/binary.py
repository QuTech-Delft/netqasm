from netqasm import encoding
from netqasm.instructions import Instruction, COMMAND_STRUCTS
from netqasm import subroutine
from netqasm.subroutine import (
    Command,
    Register,
    Address,
    Subroutine,
    ArrayEntry,
    ArraySlice,
)


def parse_binary_subroutine(data: bytes) -> Subroutine:
    metadata, data = parse_metadata(data)
    if (len(data) % encoding.COMMAND_BYTES) != 0:
        raise ValueError("Length of data not a multiple of command length")
    num_commands = int(len(data) / encoding.COMMAND_BYTES)
    commands = [
        parse_binary_command(data[i * encoding.COMMAND_BYTES:(i + 1) * encoding.COMMAND_BYTES])
        for i in range(num_commands)]
    return Subroutine(
        netqasm_version=tuple(metadata.netqasm_version),
        app_id=metadata.app_id,
        commands=commands,
    )


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
