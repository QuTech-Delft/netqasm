import pytest

from netqasm.subroutine import (
    Command,
    Subroutine,
)
from netqasm.encoding import RegisterName
from netqasm.parsing import parse_text_subroutine
from netqasm.util import NetQASMInstrError, NetQASMSyntaxError
from netqasm.instructions import Instruction

from netqasm import instr2
from netqasm.instr2.operand import (
    Register,
    Immediate,
    Address,
    ArrayEntry,
    ArraySlice,
)


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
            instr2.core.SetInstruction(
                reg=Register(RegisterName.R, 0),
                value=Immediate(0),
            ),
            instr2.core.StoreInstruction(
                reg=Register(RegisterName.R, 0),
                entry=ArrayEntry(Address(0), Register(RegisterName.R, 2)),
            ),
            instr2.core.SetInstruction(
                reg=Register(RegisterName.Q, 0),
                value=Immediate(0),
            ),
            instr2.core.InitInstruction(
                qreg=Register(RegisterName.Q, 0),
            ),
            instr2.core.SetInstruction(
                reg=Register(RegisterName.R, 3),
                value=Immediate(4),
            ),
            instr2.core.ArrayInstruction(
                size=Register(RegisterName.R, 3),
                address=Address(address=2),
            ),
            instr2.core.SetInstruction(
                reg=Register(RegisterName.R, 3),
                value=Immediate(1),
            ),
            instr2.core.AddInstruction(
                regout=Register(RegisterName.R, 1),
                reg0=Register(RegisterName.R, 2),
                reg1=Register(RegisterName.R, 3),
            ),
            instr2.core.SetInstruction(
                reg=Register(RegisterName.R, 3),
                value=Immediate(0),
            ),
            instr2.core.SetInstruction(
                reg=Register(RegisterName.R, 4),
                value=Immediate(0),
            ),
            instr2.core.BeqInstruction(
                reg0=Register(RegisterName.R, 3),
                reg1=Register(RegisterName.R, 4),
                line=Immediate(11),
            ),
            instr2.core.RetRegInstruction(
                reg=Register(RegisterName.R, 0),
            ),
            instr2.core.SetInstruction(
                reg=Register(RegisterName.R, 3),
                value=Immediate(0),
            ),
            instr2.core.SetInstruction(
                reg=Register(RegisterName.R, 4),
                value=Immediate(1),
            ),
            instr2.core.RetArrInstruction(
                address=ArraySlice(
                    Address(0),
                    Register(RegisterName.R, 3),
                    Register(RegisterName.R, 4),
                ),
            ),
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
            instr2.core.SetInstruction(
                reg=Register(RegisterName.C, 1),
                value=Immediate(1),
            ),
            instr2.core.SetInstruction(
                reg=Register(RegisterName.C, 10),
                value=Immediate(10),
            ),
            instr2.core.SetInstruction(
                reg=Register(RegisterName.Q, 0),
                value=Immediate(0),
            ),
            instr2.core.SetInstruction(
                reg=Register(RegisterName.R, 0),
                value=Immediate(0),
            ),
            instr2.core.ArrayInstruction(
                size=Register(RegisterName.C, 10),
                address=Address(0),
            ),
            instr2.core.BeqInstruction(
                reg0=Register(RegisterName.R, 0),
                reg1=Register(RegisterName.C, 10),
                line=Immediate(14),
            ),
            instr2.core.QAllocInstruction(
                qreg=Register(RegisterName.Q, 0),
            ),
            instr2.core.InitInstruction(
                qreg=Register(RegisterName.Q, 0),
            ),
            instr2.vanilla.GateHInstruction(
                qreg=Register(RegisterName.Q, 0),
            ),
            instr2.core.MeasInstruction(
                qreg=Register(RegisterName.Q, 0),
                creg=Register(RegisterName.M, 0),
            ),
            instr2.core.StoreInstruction(
                reg=Register(RegisterName.M, 0),
                entry=ArrayEntry(
                    address=Address(0),
                    index=Register(RegisterName.R, 0),
                ),
            ),
            instr2.core.QFreeInstruction(
                qreg=Register(RegisterName.Q, 0),
            ),
            instr2.core.AddInstruction(
                regout=Register(RegisterName.R, 0),
                reg0=Register(RegisterName.R, 0),
                reg1=Register(RegisterName.C, 1),
            ),
            instr2.core.JmpInstruction(
                line=Immediate(5),
            ),
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


def test_rotations():
    subroutine = """
# NETQASM 0.0
# APPID 0

set Q0 0
qalloc Q0
init Q0

// Perform rotations
rot_x Q0 1 1  // rotate by 1 * pi / 1 = pi
rot_x Q0 1 4  // rotate by 1 * pi / 4 = pi / 4
rot_y Q0 7 22  // rotate by 7 pi / 22

qfree Q0
"""

    expected = Subroutine(
        netqasm_version=(0, 0),
        app_id=0,
        commands=[
            instr2.core.SetInstruction(
                reg=Register(RegisterName.Q, 0),
                value=Immediate(0),
            ),
            instr2.core.QAllocInstruction(
                qreg=Register(RegisterName.Q, 0),
            ),
            instr2.core.InitInstruction(
                qreg=Register(RegisterName.Q, 0),
            ),
            # Rotations
            instr2.vanilla.RotXInstruction(
                qreg=Register(RegisterName.Q, 0),
                angle_num=Immediate(1),
                angle_denom=Immediate(1),
            ),
            instr2.vanilla.RotXInstruction(
                qreg=Register(RegisterName.Q, 0),
                angle_num=Immediate(1),
                angle_denom=Immediate(4),
            ),
            instr2.vanilla.RotYInstruction(
                qreg=Register(RegisterName.Q, 0),
                angle_num=Immediate(7),
                angle_denom=Immediate(22),
            ),
            instr2.core.QFreeInstruction(
                qreg=Register(RegisterName.Q, 0),
            ),
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
    test_rotations()
