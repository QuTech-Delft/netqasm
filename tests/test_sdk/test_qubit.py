import logging

from netqasm.sdk.connection import NetQASMConnection
from netqasm.sdk.qubit import Qubit
from netqasm.subroutine import Subroutine, Command, Register, Constant
from netqasm.encoding import RegisterName
from netqasm.instructions import Instruction
from netqasm.parsing import parse_binary_subroutine

storage = []


class DebugConnection(NetQASMConnection):
    def commit(self, subroutine, block=True):
        storage.append(subroutine)


def test():
    logging.basicConfig(level=logging.DEBUG)
    with DebugConnection("Alice") as alice:
        q1 = Qubit(alice)
        q2 = Qubit(alice)
        q1.H()
        q2.X()
        q1.X()
        q2.H()

    assert len(storage) == 1
    subroutine = parse_binary_subroutine(storage[0])
    expected = Subroutine(netqasm_version='0.0', app_id=0, commands=[
        Command(instruction=Instruction.SET, args=[], operands=[
            Register(RegisterName.Q, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.QALLOC, args=[], operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.INIT, args=[], operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, args=[], operands=[
            Register(RegisterName.Q, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.QALLOC, args=[], operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.INIT, args=[], operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, args=[], operands=[
            Register(RegisterName.Q, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.H, args=[], operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, args=[], operands=[
            Register(RegisterName.Q, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.X, args=[], operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, args=[], operands=[
            Register(RegisterName.Q, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.X, args=[], operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, args=[], operands=[
            Register(RegisterName.Q, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.H, args=[], operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, args=[], operands=[
            Register(RegisterName.Q, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.QFREE, args=[], operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, args=[], operands=[
            Register(RegisterName.Q, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.QFREE, args=[], operands=[
            Register(RegisterName.Q, 0),
        ]),
    ])
    for command, expected_command in zip(subroutine.commands, expected.commands):
        print(repr(command))
        print(repr(expected_command))
        assert command == expected_command
    print(subroutine)
    print(expected)
    assert subroutine == expected
