import pytest

# from netqasm.parser import Parser, Subroutine, Command, Address, AddressMode, QubitAddress, Array
from netqasm.subroutine import (
    Constant,
    RegisterName,
    Register,
    MemoryAddress,
    Command,
    BranchLabel,
    Subroutine,
)
from netqasm.parser import parse_subroutine
from netqasm.util import NetQASMInstrError, NetQASMSyntaxError


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
        parse_subroutine(subroutine)


def test_simple():
    subroutine = """
# NETQASM 0.0
# APPID 0
set R0 0
store 1 @0
store 1 @R0
store R0 @1
store R0 @R0
store R0 @0[0]
store R0 @R0[R1]
set Q0 0
init Q0
array(4) @2
add R1 R2 1
beq 0 0 EXIT
EXIT:
"""

    expected = Subroutine(
        netqasm_version="0.0",
        app_id=0,
        commands=[
            Command(instruction="set", args=[], operands=[
                Register(RegisterName.R, Constant(0)),
                Constant(0),
            ]),
            Command(instruction="store", args=[], operands=[
                Constant(1),
                MemoryAddress(
                    base_address=Constant(0),
                    index=None,
                ),
            ]),
            Command(instruction="store", args=[], operands=[
                Constant(1),
                MemoryAddress(
                    base_address=Register(RegisterName.R, Constant(0)),
                    index=None,
                ),
            ]),
            Command(instruction="store", args=[], operands=[
                Register(RegisterName.R, Constant(0)),
                MemoryAddress(
                    base_address=Constant(1),
                    index=None,
                ),
            ]),
            Command(instruction="store", args=[], operands=[
                Register(RegisterName.R, Constant(0)),
                MemoryAddress(
                    base_address=Register(RegisterName.R, Constant(0)),
                    index=None,
                ),
            ]),
            Command(instruction="store", args=[], operands=[
                Register(RegisterName.R, Constant(0)),
                MemoryAddress(
                    base_address=Constant(0),
                    index=Constant(0),
                ),
            ]),
            Command(instruction="store", args=[], operands=[
                Register(RegisterName.R, Constant(0)),
                MemoryAddress(
                    base_address=Register(RegisterName.R, Constant(0)),
                    index=Register(RegisterName.R, Constant(1)),
                ),
            ]),
            Command(instruction="set", args=[], operands=[
                Register(RegisterName.Q, Constant(0)),
                Constant(0),
            ]),
            Command(instruction="init", args=[], operands=[
                Register(RegisterName.Q, Constant(0)),
            ]),
            Command(instruction="array", args=[Constant(4)], operands=[
                MemoryAddress(
                    base_address=Constant(2),
                    index=None,
                ),
            ]),
            Command(instruction="add", args=[], operands=[
                Register(RegisterName.R, Constant(1)),
                Register(RegisterName.R, Constant(2)),
                Constant(1),
            ]),
            Command(instruction="beq", args=[], operands=[
                Constant(0),
                Constant(0),
                Constant(12),
            ]),
        ])

    subroutine = parse_subroutine(subroutine)
    for i, command in enumerate(subroutine.commands):
        exp_command = expected.commands[i]
        print(command)
        print(exp_command)
        assert command == exp_command
    print(repr(subroutine))
    print(repr(expected))
    assert subroutine == expected


def test_loop():
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
"""

    expected = Subroutine(
        netqasm_version="0.0",
        app_id=0,
        commands=[
            Command(instruction="set", args=[], operands=[
                Register(RegisterName.Q, Constant(0)),
                Constant(0),
            ]),
            Command(instruction="array", args=[Constant(10)], operands=[
                MemoryAddress(
                    base_address=Constant(0),
                    index=None,
                ),
            ]),
            Command(instruction="set", args=[], operands=[
                Register(RegisterName.R, Constant(0)),
                Constant(0),
            ]),
            Command(instruction="beq", args=[], operands=[
                Register(RegisterName.R, Constant(0)),
                Constant(10),
                Constant(12),
            ]),
            Command(instruction="qalloc", args=[], operands=[
                Register(RegisterName.Q, Constant(0)),
            ]),
            Command(instruction="init", args=[], operands=[
                Register(RegisterName.Q, Constant(0)),
            ]),
            Command(instruction="h", args=[], operands=[
                Register(RegisterName.Q, Constant(0)),
            ]),
            Command(instruction="meas", args=[], operands=[
                Register(RegisterName.Q, Constant(0)),
                Register(RegisterName.M, Constant(0)),
            ]),
            Command(instruction="store", args=[], operands=[
                Register(RegisterName.M, Constant(0)),
                MemoryAddress(
                    base_address=Constant(0),
                    index=Register(RegisterName.R, Constant(0)),
                ),
            ]),
            Command(instruction="qfree", args=[], operands=[
                Register(RegisterName.Q, Constant(0)),
            ]),
            Command(instruction="add", args=[], operands=[
                Register(RegisterName.R, Constant(0)),
                Register(RegisterName.R, Constant(0)),
                Constant(1),
            ]),
            Command(instruction="beq", args=[], operands=[
                Constant(0),
                Constant(0),
                Constant(3),
            ]),
        ],
    )
    subroutine = parse_subroutine(subroutine)
    for i, command in enumerate(subroutine.commands):
        exp_command = expected.commands[i]
        print(command)
        print(exp_command)
        assert command == exp_command
    print(repr(subroutine))
    print(repr(expected))
    assert subroutine == expected


if __name__ == "__main__":
    test_simple()
    test_loop()
