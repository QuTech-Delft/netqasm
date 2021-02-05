import logging

from qlink_interface import EPRType

from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.logging.glob import set_log_level
from netqasm.lang.subroutine import Subroutine
from netqasm.lang.encoding import RegisterName
from netqasm.backend.messages import deserialize_host_msg as deserialize_message
from netqasm.lang.parsing import deserialize as deserialize_subroutine
from netqasm.backend.network_stack import CREATE_FIELDS, OK_FIELDS

from netqasm.lang import instr as instructions
from netqasm.lang.instr.operand import (
    Register,
    Immediate,
    Address,
    ArrayEntry,
    ArraySlice,
)

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
    raw_subroutine = deserialize_message(raw=alice.storage[1]).subroutine
    subroutine = deserialize_subroutine(raw_subroutine)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(0),
        ),
        instructions.core.QAllocInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        instructions.core.InitInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(1),
        ),
        instructions.core.QAllocInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        instructions.core.InitInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(0),
        ),
        instructions.vanilla.GateHInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(1),
        ),
        instructions.vanilla.GateXInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(0),
        ),
        instructions.vanilla.GateXInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(1),
        ),
        instructions.vanilla.GateHInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
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
    raw_subroutine = deserialize_message(raw=alice.storage[1]).subroutine
    subroutine = deserialize_subroutine(raw_subroutine)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(0),
        ),
        instructions.core.QAllocInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        instructions.core.InitInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(0),
        ),
        instructions.vanilla.RotXInstruction(
            reg=Register(RegisterName.Q, 0),
            imm0=Immediate(1),
            imm1=Immediate(1),
        ),
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

    epr_socket = EPRSocket(remote_app_name="Bob")
    with DebugConnection("Alice", epr_sockets=[epr_socket]) as alice:
        q1 = epr_socket.create()[0]
        q1.H()

    # 5 messages: init, open_epr_socket, subroutine, stop app and stop backend
    assert len(alice.storage) == 5
    raw_subroutine = deserialize_message(raw=alice.storage[2]).subroutine
    subroutine = deserialize_subroutine(raw_subroutine)
    print(subroutine)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        # Arg array
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(OK_FIELDS),
        ),
        instructions.core.ArrayInstruction(
            reg=Register(RegisterName.R, 0),
            address=Address(0),
        ),
        # Qubit address array
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(1),
        ),
        instructions.core.ArrayInstruction(
            reg=Register(RegisterName.R, 0),
            address=Address(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(0),
        ),
        instructions.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(1, index=Register(RegisterName.R, 1)),
        ),
        # ent info array
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(CREATE_FIELDS),
        ),
        instructions.core.ArrayInstruction(
            reg=Register(RegisterName.R, 0),
            address=Address(2),
        ),
        # tp arg
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(0),
        ),
        instructions.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ),
        # num pairs arg
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(1),
        ),
        instructions.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ),
        # create cmd
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            imm=Immediate(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 3),
            imm=Immediate(2),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 4),
            imm=Immediate(0),
        ),
        instructions.core.CreateEPRInstruction(
            reg0=Register(RegisterName.R, 0),
            reg1=Register(RegisterName.R, 1),
            reg2=Register(RegisterName.R, 2),
            reg3=Register(RegisterName.R, 3),
            reg4=Register(RegisterName.R, 4),
        ),
        # wait cmd
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(OK_FIELDS),
        ),
        instructions.core.WaitAllInstruction(
            slice=ArraySlice(
                address=Address(0),
                start=Register(RegisterName.R, 0),
                stop=Register(RegisterName.R, 1),
            ),
        ),
        # Hadamard
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(0),
        ),
        instructions.vanilla.GateHInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
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
        instructions.core.RetArrInstruction(
            address=Address(0),
        ),
        instructions.core.RetArrInstruction(
            address=Address(1),
        ),
        instructions.core.RetArrInstruction(
            address=Address(2),
        ),
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

    epr_socket = EPRSocket(remote_app_name="Bob")
    with DebugConnection("Alice", epr_sockets=[epr_socket]) as alice:
        qubits = epr_socket.create(number=2)
        qubits[0].H()
        qubits[1].H()

    # 5 messages: init, open_epr_socket, subroutine, stop app and stop backend
    assert len(alice.storage) == 5
    raw_subroutine = deserialize_message(raw=alice.storage[2]).subroutine
    subroutine = deserialize_subroutine(raw_subroutine)
    print(subroutine)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        # Arg array
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(2 * OK_FIELDS),
        ),
        instructions.core.ArrayInstruction(
            reg=Register(RegisterName.R, 0),
            address=Address(0),
        ),
        # Qubit address array
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(2),
        ),
        instructions.core.ArrayInstruction(
            reg=Register(RegisterName.R, 0),
            address=Address(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(0),
        ),
        instructions.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(1, index=Register(RegisterName.R, 1)),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(1),
        ),
        instructions.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(1, index=Register(RegisterName.R, 1)),
        ),
        # ent info array
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(CREATE_FIELDS),
        ),
        instructions.core.ArrayInstruction(
            reg=Register(RegisterName.R, 0),
            address=Address(2),
        ),
        # tp arg
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(0),
        ),
        instructions.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ),
        # num pairs arg
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(2),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(1),
        ),
        instructions.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ),
        # create cmd
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            imm=Immediate(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 3),
            imm=Immediate(2),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 4),
            imm=Immediate(0),
        ),
        instructions.core.CreateEPRInstruction(
            reg0=Register(RegisterName.R, 0),
            reg1=Register(RegisterName.R, 1),
            reg2=Register(RegisterName.R, 2),
            reg3=Register(RegisterName.R, 3),
            reg4=Register(RegisterName.R, 4),
        ),
        # wait cmd
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            imm=Immediate(0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(2 * OK_FIELDS),
        ),
        instructions.core.WaitAllInstruction(
            slice=ArraySlice(
                address=Address(0),
                start=Register(RegisterName.R, 0),
                stop=Register(RegisterName.R, 1),
            ),
        ),
        # Hadamards
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(0),
        ),
        instructions.vanilla.GateHInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            imm=Immediate(1),
        ),
        instructions.vanilla.GateHInstruction(
            reg=Register(RegisterName.Q, 0),
        ),
        # return cmds
        instructions.core.RetArrInstruction(
            address=Address(0),
        ),
        instructions.core.RetArrInstruction(
            address=Address(1),
        ),
        instructions.core.RetArrInstruction(
            address=Address(2),
        ),
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

    epr_socket = EPRSocket(remote_app_name="Bob")
    with DebugConnection("Alice", epr_sockets=[epr_socket]) as alice:
        outcomes = epr_socket.create(tp=EPRType.M)
        m = outcomes[0][2]
        with m.if_eq(0):
            m.add(1)

    # 5 messages: init, open_epr_socket, subroutine, stop app and stop backend
    assert len(alice.storage) == 5
    raw_subroutine = deserialize_message(raw=alice.storage[2]).subroutine
    subroutine = deserialize_subroutine(raw_subroutine)
    print(subroutine)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
        # Arg array
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(OK_FIELDS),
        ),
        instructions.core.ArrayInstruction(
            reg=Register(RegisterName.R, 1),
            address=Address(0),
        ),
        # ent info array
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(CREATE_FIELDS),
        ),
        instructions.core.ArrayInstruction(
            reg=Register(RegisterName.R, 1),
            address=Address(1),
        ),
        # tp arg
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            imm=Immediate(0),
        ),
        instructions.core.StoreInstruction(
            reg=Register(RegisterName.R, 1),
            entry=ArrayEntry(1, index=Register(RegisterName.R, 2)),
        ),
        # num pairs arg
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            imm=Immediate(1),
        ),
        instructions.core.StoreInstruction(
            reg=Register(RegisterName.R, 1),
            entry=ArrayEntry(1, index=Register(RegisterName.R, 2)),
        ),
        # create cmd
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            imm=Immediate(0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 3),
            imm=Immediate(1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 4),
            imm=Immediate(0),
        ),
        instructions.core.CreateEPRInstruction(
            reg0=Register(RegisterName.R, 1),
            reg1=Register(RegisterName.R, 2),
            reg2=Register(RegisterName.C, 0),
            reg3=Register(RegisterName.R, 3),
            reg4=Register(RegisterName.R, 4),
        ),
        # wait cmd
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(0),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            imm=Immediate(OK_FIELDS),
        ),
        instructions.core.WaitAllInstruction(
            slice=ArraySlice(
                address=Address(0),
                start=Register(RegisterName.R, 1),
                stop=Register(RegisterName.R, 2),
            ),
        ),
        # if statement
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(2),
        ),
        instructions.core.LoadInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(
                address=Address(0),
                index=Register(RegisterName.R, 1),
            ),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(0),
        ),
        instructions.core.BneInstruction(
            reg0=Register(RegisterName.R, 0),
            reg1=Register(RegisterName.R, 1),
            imm=Immediate(28),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(2),
        ),
        instructions.core.LoadInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(
                address=Address(0),
                index=Register(RegisterName.R, 1),
            ),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(1),
        ),
        instructions.core.AddInstruction(
            reg0=Register(RegisterName.R, 0),
            reg1=Register(RegisterName.R, 0),
            reg2=Register(RegisterName.R, 1),
        ),
        instructions.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            imm=Immediate(2),
        ),
        instructions.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(
                address=Address(0),
                index=Register(RegisterName.R, 1),
            ),
        ),
        # return cmds
        instructions.core.RetArrInstruction(
            address=Address(0),
        ),
        instructions.core.RetArrInstruction(
            address=Address(1),
        ),
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
    test_simple()
    test_rotations()
    test_epr()
    test_two_epr()
    test_epr_m()
