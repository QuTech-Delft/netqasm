import logging

from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.epr_socket import EPRSocket, EPRType
from netqasm.logging import set_log_level
from netqasm.subroutine import (
    Subroutine,
    Command,
    Register,
    Address,
    ArrayEntry,
    ArraySlice,
)
from netqasm.encoding import RegisterName
from netqasm.instructions import Instruction
from netqasm.parsing import parse_binary_subroutine
from netqasm.network_stack import CREATE_FIELDS, OK_FIELDS


DebugConnection.node_ids = {
    "Alice": 0,
    "Bob": 1,
}


def test_simple():
    set_log_level(logging.DEBUG)
    with DebugConnection("Alice") as alice:
        q1 = Qubit(alice)
        q2 = Qubit(alice)
        q1.H()
        q2.X()
        q1.X()
        q2.H()

    # 4 messages: init, subroutine, stop app and stop backend
    assert len(alice.storage) == 4
    subroutine = parse_binary_subroutine(alice.storage[1].msg)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            0,
        ]),
        Command(instruction=Instruction.QALLOC, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.INIT, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            1,
        ]),
        Command(instruction=Instruction.QALLOC, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.INIT, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            0,
        ]),
        Command(instruction=Instruction.H, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            1,
        ]),
        Command(instruction=Instruction.X, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            0,
        ]),
        Command(instruction=Instruction.X, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            1,
        ]),
        Command(instruction=Instruction.H, operands=[
            Register(RegisterName.Q, 0),
        ]),
        # NOTE qubits are now freed when application ends
        # without explicit qfree for each
        # Command(instruction=Instruction.SET, operands=[
        #     Register(RegisterName.Q, 0),
        #     0,
        # ]),
        # Command(instruction=Instruction.QFREE, operands=[
        #     Register(RegisterName.Q, 0),
        # ]),
        # Command(instruction=Instruction.SET, operands=[
        #     Register(RegisterName.Q, 0),
        #     1,
        # ]),
        # Command(instruction=Instruction.QFREE, operands=[
        #     Register(RegisterName.Q, 0),
        # ]),
    ])
    for command, expected_command in zip(subroutine.commands, expected.commands):
        print(repr(command))
        print(repr(expected_command))
        assert command == expected_command
    print(subroutine)
    print(expected)
    assert subroutine == expected


def test_rotations():
    set_log_level(logging.DEBUG)
    with DebugConnection("Alice") as alice:
        q = Qubit(alice)
        q.rot_X(n=1, d=1)

    # 4 messages: init, subroutine, stop app and stop backend
    assert len(alice.storage) == 4
    subroutine = parse_binary_subroutine(alice.storage[1].msg)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            0,
        ]),
        Command(instruction=Instruction.QALLOC, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.INIT, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            0,
        ]),
        Command(instruction=Instruction.ROT_X, operands=[
            Register(RegisterName.Q, 0),
            1,
            1,
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

    set_log_level(logging.DEBUG)

    epr_socket = EPRSocket(remote_node_name="Bob")
    with DebugConnection("Alice", epr_sockets=[epr_socket]) as alice:
        q1 = epr_socket.create()[0]
        q1.H()

    # 5 messages: init, open_epr_socket, subroutine, stop app and stop backend
    assert len(alice.storage) == 5
    subroutine = parse_binary_subroutine(alice.storage[2].msg)
    print(subroutine)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        # Arg array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            OK_FIELDS,
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 0),
            Address(0),
        ]),
        # Qubit address array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            1,
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 0),
            Address(1),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            0,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            0,
        ]),
        Command(instruction=Instruction.STORE, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(1, index=Register(RegisterName.R, 1)),
        ]),
        # ent info array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            CREATE_FIELDS,
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 0),
            Address(2),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            1,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            1,
        ]),
        Command(instruction=Instruction.STORE, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ]),
        # create cmd
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            1,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            0,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 2),
            1,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 3),
            2,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 4),
            0,
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
            0,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            OK_FIELDS,
        ]),
        Command(instruction=Instruction.WAIT_ALL, operands=[
            ArraySlice(
                address=Address(0),
                start=Register(RegisterName.R, 0),
                stop=Register(RegisterName.R, 1),
            ),
        ]),
        # Hadamard
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            0,
        ]),
        Command(instruction=Instruction.H, operands=[
            Register(RegisterName.Q, 0),
        ]),
        # free qubit
        # NOTE qubits are now freed when application ends
        # without explicit qfree for each
        # Command(instruction=Instruction.SET, operands=[
        #     Register(RegisterName.Q, 0),
        #     0,
        # ]),
        # Command(instruction=Instruction.QFREE, operands=[
        #     Register(RegisterName.Q, 0),
        # ]),
        # return cmds
        Command(instruction=Instruction.RET_ARR, operands=[
            Address(0),
        ]),
        Command(instruction=Instruction.RET_ARR, operands=[
            Address(1),
        ]),
        Command(instruction=Instruction.RET_ARR, operands=[
            Address(2),
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


def test_two_epr():

    set_log_level(logging.DEBUG)

    epr_socket = EPRSocket(remote_node_name="Bob")
    with DebugConnection("Alice", epr_sockets=[epr_socket]) as alice:
        qubits = epr_socket.create(number=2)
        qubits[0].H()
        qubits[1].H()

    # 5 messages: init, open_epr_socket, subroutine, stop app and stop backend
    assert len(alice.storage) == 5
    subroutine = parse_binary_subroutine(alice.storage[2].msg)
    print(subroutine)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        # Arg array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            2 * OK_FIELDS,
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 0),
            Address(0),
        ]),
        # Qubit address array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            2,
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 0),
            Address(1),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            0,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            0,
        ]),
        Command(instruction=Instruction.STORE, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(1, index=Register(RegisterName.R, 1)),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            1,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            1,
        ]),
        Command(instruction=Instruction.STORE, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(1, index=Register(RegisterName.R, 1)),
        ]),
        # ent info array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            CREATE_FIELDS,
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 0),
            Address(2),
        ]),
        # tp arg
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            0,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            0,
        ]),
        Command(instruction=Instruction.STORE, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ]),
        # num pairs arg
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            2,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            1,
        ]),
        Command(instruction=Instruction.STORE, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ]),
        # create cmd
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 0),
            1,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            0,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 2),
            1,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 3),
            2,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 4),
            0,
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
            0,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            2 * OK_FIELDS,
        ]),
        Command(instruction=Instruction.WAIT_ALL, operands=[
            ArraySlice(
                address=Address(0),
                start=Register(RegisterName.R, 0),
                stop=Register(RegisterName.R, 1),
            ),
        ]),
        # Hadamards
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            0,
        ]),
        Command(instruction=Instruction.H, operands=[
            Register(RegisterName.Q, 0),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.Q, 0),
            1,
        ]),
        Command(instruction=Instruction.H, operands=[
            Register(RegisterName.Q, 0),
        ]),
        # return cmds
        Command(instruction=Instruction.RET_ARR, operands=[
            Address(0),
        ]),
        Command(instruction=Instruction.RET_ARR, operands=[
            Address(1),
        ]),
        Command(instruction=Instruction.RET_ARR, operands=[
            Address(2),
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


def test_epr_m():

    set_log_level(logging.DEBUG)

    epr_socket = EPRSocket(remote_node_name="Bob")
    with DebugConnection("Alice", epr_sockets=[epr_socket]) as alice:
        outcomes = epr_socket.create(tp=EPRType.M)
        m = outcomes[0][2]
        with m.if_eq(0):
            m.add(1)

    # 5 messages: init, open_epr_socket, subroutine, stop app and stop backend
    assert len(alice.storage) == 5
    subroutine = parse_binary_subroutine(alice.storage[2].msg)
    print(subroutine)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        # Arg array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            OK_FIELDS,
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 1),
            Address(0),
        ]),
        # ent info array
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            CREATE_FIELDS,
        ]),
        Command(instruction=Instruction.ARRAY, operands=[
            Register(RegisterName.R, 1),
            Address(1),
        ]),
        # tp arg
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            1,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 2),
            0,
        ]),
        Command(instruction=Instruction.STORE, operands=[
            Register(RegisterName.R, 1),
            ArrayEntry(1, index=Register(RegisterName.R, 2)),
        ]),
        # num pairs arg
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            1,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 2),
            1,
        ]),
        Command(instruction=Instruction.STORE, operands=[
            Register(RegisterName.R, 1),
            ArrayEntry(1, index=Register(RegisterName.R, 2)),
        ]),
        # create cmd
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            1,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 2),
            0,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 3),
            1,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 4),
            0,
        ]),
        Command(instruction=Instruction.CREATE_EPR, operands=[
            Register(RegisterName.R, 1),
            Register(RegisterName.R, 2),
            Register(RegisterName.C, 0),
            Register(RegisterName.R, 3),
            Register(RegisterName.R, 4),
        ]),
        # wait cmd
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            0,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 2),
            OK_FIELDS,
        ]),
        Command(instruction=Instruction.WAIT_ALL, operands=[
            ArraySlice(
                address=Address(0),
                start=Register(RegisterName.R, 1),
                stop=Register(RegisterName.R, 2),
            ),
        ]),
        # if statement
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            2,
        ]),
        Command(Instruction.LOAD, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(
                address=Address(0),
                index=Register(RegisterName.R, 1),
            ),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            0,
        ]),
        Command(instruction=Instruction.BNE, operands=[
            Register(RegisterName.R, 0),
            Register(RegisterName.R, 1),
            28,
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            2,
        ]),
        Command(Instruction.LOAD, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(
                address=Address(0),
                index=Register(RegisterName.R, 1),
            ),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            1,
        ]),
        Command(instruction=Instruction.ADD, operands=[
            Register(RegisterName.R, 0),
            Register(RegisterName.R, 0),
            Register(RegisterName.R, 1),
        ]),
        Command(instruction=Instruction.SET, operands=[
            Register(RegisterName.R, 1),
            2,
        ]),
        Command(Instruction.STORE, operands=[
            Register(RegisterName.R, 0),
            ArrayEntry(
                address=Address(0),
                index=Register(RegisterName.R, 1),
            ),
        ]),
        # return cmds
        Command(instruction=Instruction.RET_ARR, operands=[
            Address(0),
        ]),
        Command(instruction=Instruction.RET_ARR, operands=[
            Address(1),
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
    # test_rotations()
    # test_epr()
    # test_two_epr()
    test_epr_m()
