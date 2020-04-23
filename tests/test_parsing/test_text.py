import pytest

from netqasm.subroutine import (
    Constant,
    Register,
    Address,
    ArrayEntry,
    ArraySlice,
    Command,
    Subroutine,
)
from netqasm.encoding import RegisterName
from netqasm.parsing import parse_text_subroutine
from netqasm.util import NetQASMInstrError, NetQASMSyntaxError
from netqasm.instructions import Instruction


@pytest.mark.parametrize("subroutine, error", [
    ("# WRONG", NetQASMInstrError),  # Wrong keyword
    ("# APPID 0\nH 0\n#APPID 0", NetQASMSyntaxError),  # Preamble after body
    ("# DEFINE args {0, 0", NetQASMSyntaxError),  # No end-bracket
    ("# NETQASM", NetQASMSyntaxError),  # No argument
    ("# NETQASM 1 2", NetQASMSyntaxError),  # Two arguments
    ("# APPID", NetQASMSyntaxError),  # No argument
    ("# APPID 1 2", NetQASMSyntaxError),  # Two arguments
    ("# DEFINE args", NetQASMSyntaxError),  # One arguments
    ("# DEFINE args 0 0", NetQASMSyntaxError),  # Three arguments
    ("# DEFINE 1args 0", NetQASMInstrError),  # Not a valid macro key
    ("# DEFINE args 0\n# DEFINE args 1", NetQASMInstrError),  # Not unique macro keys
])
def test_faulty_preamble(subroutine, error):
    with pytest.raises(error):
        parse_text_subroutine(subroutine)


def test_simple():
    subroutine = """
# NETQASM 0.0
# APPID 0
set R0 0
store R0 @0[R2]
set Q0 0
init Q0
array(4) @2
add R1 R2 1
beq 0 0 EXIT
EXIT:
ret_reg R0
ret_arr @0[0:1]
"""

    expected = Subroutine(
        netqasm_version=(0, 0),
        app_id=0,
        commands=[
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.R, 0),
                Constant(0),
            ]),
            Command(instruction=Instruction.STORE, operands=[
                Register(RegisterName.R, 0),
                ArrayEntry(Address(Constant(0)), Register(RegisterName.R, 2)),
            ]),
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.Q, 0),
                Constant(0),
            ]),
            Command(instruction=Instruction.INIT, operands=[
                Register(RegisterName.Q, 0),
            ]),
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.R, 3),
                Constant(4),
            ]),
            Command(instruction=Instruction.ARRAY, operands=[
                Register(RegisterName.R, 3),
                Address(address=Constant(2)),
            ]),
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.R, 3),
                Constant(1),
            ]),
            Command(instruction=Instruction.ADD, operands=[
                Register(RegisterName.R, 1),
                Register(RegisterName.R, 2),
                Register(RegisterName.R, 3),
            ]),
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.R, 3),
                Constant(0),
            ]),
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.R, 4),
                Constant(0),
            ]),
            Command(instruction=Instruction.BEQ, operands=[
                Register(RegisterName.R, 3),
                Register(RegisterName.R, 4),
                Constant(11),
            ]),
            Command(instruction=Instruction.RET_REG, operands=[
                Register(RegisterName.R, 0),
            ]),
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.R, 3),
                Constant(0),
            ]),
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.R, 4),
                Constant(1),
            ]),
            Command(instruction=Instruction.RET_ARR, operands=[
                ArraySlice(
                    Address(Constant(0)),
                    Register(RegisterName.R, 3),
                    Register(RegisterName.R, 4),
                ),
            ]),
        ])

    subroutine = parse_text_subroutine(subroutine)
    print(subroutine)
    for i, command in enumerate(subroutine.commands):
        exp_command = expected.commands[i]
        print(repr(command))
        print(repr(exp_command))
        assert command == exp_command
    print(repr(subroutine))
    print(repr(expected))
    assert subroutine == expected


def test_loop():
    subroutine = """
# NETQASM 0.0
# APPID 0
# DEFINE ms @0
// Setup constants
set C1 1
set C10 10
// Setup classical registers
set Q0 0
set R0 0
array C10 ms!

// Loop entry
LOOP:
beq R0 C10 EXIT

// Loop body
qalloc Q0
init Q0
h Q0
meas Q0 M0

// Store to array
store M0 ms![R0]

qfree Q0
add R0 R0 C1

// Loop exit
jmp LOOP
EXIT:
"""

    expected = Subroutine(
        netqasm_version=(0, 0),
        app_id=0,
        commands=[
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.C, 1),
                Constant(1),
            ]),
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.C, 10),
                Constant(10),
            ]),
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.Q, 0),
                Constant(0),
            ]),
            Command(instruction=Instruction.SET, operands=[
                Register(RegisterName.R, 0),
                Constant(0),
            ]),
            Command(instruction=Instruction.ARRAY, operands=[
                Register(RegisterName.C, 10),
                Address(Constant(0)),
            ]),
            Command(instruction=Instruction.BEQ, operands=[
                Register(RegisterName.R, 0),
                Register(RegisterName.C, 10),
                Constant(14),
            ]),
            Command(instruction=Instruction.QALLOC, operands=[
                Register(RegisterName.Q, 0),
            ]),
            Command(instruction=Instruction.INIT, operands=[
                Register(RegisterName.Q, 0),
            ]),
            Command(instruction=Instruction.H, operands=[
                Register(RegisterName.Q, 0),
            ]),
            Command(instruction=Instruction.MEAS, operands=[
                Register(RegisterName.Q, 0),
                Register(RegisterName.M, 0),
            ]),
            Command(instruction=Instruction.STORE, operands=[
                Register(RegisterName.M, 0),
                ArrayEntry(
                    address=Address(Constant(0)),
                    index=Register(RegisterName.R, 0),
                ),
            ]),
            Command(instruction=Instruction.QFREE, operands=[
                Register(RegisterName.Q, 0),
            ]),
            Command(instruction=Instruction.ADD, operands=[
                Register(RegisterName.R, 0),
                Register(RegisterName.R, 0),
                Register(RegisterName.C, 1),
            ]),
            Command(instruction=Instruction.JMP, operands=[
                Constant(5),
            ]),
        ],
    )
    subroutine = parse_text_subroutine(subroutine)
    for i, command in enumerate(subroutine.commands):
        exp_command = expected.commands[i]
        print(repr(command))
        print(repr(exp_command))
        assert command == exp_command
    print(repr(subroutine))
    print(repr(expected))
    assert subroutine == expected


if __name__ == "__main__":
    test_simple()
    test_loop()
