import logging

from netqasm.sdk.connection import NetQASMConnection
from netqasm.sdk.qubit import Qubit
from netqasm.subroutine import (
    Subroutine,
    Command,
    Register,
    Constant,
    Address,
    ArrayEntry,
    ArraySlice,
)
from netqasm.encoding import RegisterName
from netqasm.instructions import Instruction
from netqasm.parsing import parse_binary_subroutine
from netqasm.network_stack import CREATE_FIELDS


class DebugConnection(NetQASMConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage = []

    def commit(self, subroutine, block=True):
        self.storage.append(subroutine)


def test_simple():
    logging.basicConfig(level=logging.DEBUG)
    with DebugConnection("Alice") as alice:
        q1 = Qubit(alice)
        q2 = Qubit(alice)
        q1.H()
        q2.X()
        q1.X()
        q2.H()

    assert len(alice.storage) == 1
    subroutine = parse_binary_subroutine(alice.storage[0])
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.QALLOC, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.INIT, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.QALLOC, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.INIT, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.H, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.X, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.X, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.H, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.QFREE, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.QFREE, operands=[
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


def test_epr():

    class MockConnection(DebugConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.nodes = {"Alice": 0, "Bob": 1}

        def _get_remote_node_id(self, name):
            return self.nodes[name]

    logging.basicConfig(level=logging.DEBUG)
    with MockConnection("Alice") as alice:
        q1 = alice.createEPR("Bob")[0]
        q1.H()

    assert len(alice.storage) == 1
    subroutine = parse_binary_subroutine(alice.storage[0])
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        # Qubit address array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 0),
            Address(1),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            Constant(0),
        ]),
        Command(instruction=Instruction.STORE, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(1, index=Register(RegisterName.R, 1)),
        ]),
        # Arg array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            Constant(CREATE_FIELDS),
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 0),
            Address(2),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            Constant(1),
        ]),
        Command(instruction=Instruction.STORE, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ]),
        # ent info array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            Constant(9),
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 0),
            Address(0),
        ]),
        # create cmd
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            Constant(1),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            Constant(0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 2),
            Constant(1),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 3),
            Constant(2),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 4),
            Constant(0),
        ]),
        Command(instruction=Instruction.CREATE_EPR, operands=[
            Register(RegisterName.R, 0),
            Register(RegisterName.R, 1),
            Register(RegisterName.R, 2),
            Register(RegisterName.R, 3),
            Register(RegisterName.R, 4),
        ]),
        # wait cmd
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            Constant(9),
        ]),
        Command(instruction=Instruction.WAIT_ALL, operands=[
            ArraySlice(
                address=Address(Constant(0)),
                start=Register(RegisterName.R, 0),
                stop=Register(RegisterName.R, 1),
            ),
        ]),
        # return cmd
        Command(instruction=Instruction.RET_ARR, operands=[
            Address(Constant(0)),
        ]),
        # Hadamard
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.H, operands=[
            Register(RegisterName.Q, 0),
        ]),
        # free qubit
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            Constant(0),
        ]),
        Command(instruction=Instruction.QFREE, operands=[
            Register(RegisterName.Q, 0),
        ]),
    ])
    for i, command in enumerate(subroutine.commands):
        print(repr(command))
        expected_command = expected.commands[i]
        print(repr(expected_command))
        print()
        assert command == expected_command
    print(subroutine)
    print(expected)
    assert subroutine == expected


if __name__ == "__main__":
    # test_simple()
    test_epr()
