from netqasm.parsing import parse_text_subroutine, parse_binary_subroutine


def test():
    subroutine = """
    # NETQASM 0.0
    # APPID 0
    # DEFINE ms @0

    // Setup classical registers
    set Q0 0
    array(10) ms!
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
    ret_reg M0
    """

    subroutine = parse_text_subroutine(subroutine)
    print(subroutine)
    data = bytes(subroutine)
    print(data)

    parsed_subroutine = parse_binary_subroutine(data)
    print(parsed_subroutine)

    for command, parsed_command in zip(subroutine.commands, parsed_subroutine.commands):
        print()
        print(repr(command))
        print(repr(parsed_command))
        assert command == parsed_command

    assert subroutine == parsed_subroutine
