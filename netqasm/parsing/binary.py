from netqasm import encoding
from netqasm.instructions import Instruction, COMMAND_STRUCTS, instruction_to_string
from netqasm.subroutine import Command, Register, Constant, Address, Subroutine
from netqasm.parsing import parse_text_subroutine



def parse_binary_subroutine(data):
    if (len(data) % encoding.COMMAND_BYTES) != 0:
        raise ValueError("Length of data not a multiple of command length")
    num_commands = int(len(data) / encoding.COMMAND_BYTES)
    commmands = [
        parse_binary_command(data[i * encoding.COMMAND_BYTES:(i + 1) * encoding.COMMAND_BYTES])
        for i in range(num_commands)]


def parse_binary_command(data):
    instruction_id = encoding.FIELD_TYPE.from_buffer_copy(data[:1]).value
    instr = Instruction(instruction_id)
    command_struct = COMMAND_STRUCTS[instr].from_buffer_copy(data)
    command = _command_struct_to_command(command_struct)
    print(command)
    return command
    pass


def _command_struct_to_command(command):
    instr_name = instruction_to_string(Instruction(command.id))
    field_values = [
        getattr(command, field_name)
        for field_name, _ in command._fields_
        if not field_name == encoding.PADDING_FIELD
    ]
    args = [_field_struct_to_arg_operand(field_value) for field_value in field_values[:command.num_args]]
    operands = [_field_struct_to_arg_operand(field_value) for field_value in field_values[command.num_args:]]

    return Command(
        instruction=instr_name,
        args=args,
        operands=operands,
    )


def _field_struct_to_arg_operand(field_value):
    if isinstance(field_value, encoding.Value):
        value = field_value.to_tp()
        if isinstance(value, encoding.Constant):
            return Constant(value=value.value)
        else:
            register_name = encoding.RegisterName(value.register_name)
            return Register(
                name=register_name,
                value=value.register_index,
            )
    elif isinstance(field_value, encoding.Address):
        if field_value.read_index:
            index = _field_struct_to_arg_operand(field_value.index)
        else:
            index = None
        base_address = _field_struct_to_arg_operand(field_value.address)
        return Address(
            base_address=base_address,
            index=index,
        )
    else:
        raise TypeError(f"Unknown field_value {field_value} of type {type(field_value)}")

def test():
    subroutine = """
    # NETQASM 0.0
    # APPID 0
    # DEFINE ms @0

    // Setup classical registers
    set Q0 0
    lea R1 ms!
    array(10) R1
    set R0 0

    // Loop entry
    LOOP:
    beq R0 10 EXIT

    // Loop body
    qalloc Q0
    init Q0
    h Q0
    meas Q0 M0

    // Store to array
    store M0 ms![R0]

    qfree Q0
    add R0 R0 1

    // Loop exit
    beq 0 0 LOOP
    EXIT:
    """

    subroutine = parse_text_subroutine(subroutine)
    print(subroutine)
    data = bytes(subroutine)

    parse_binary_subroutine(data)


if __name__ == "__main__":
    test()
