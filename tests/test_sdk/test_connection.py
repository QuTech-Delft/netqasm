
import logging

from qlink_interface import EPRType

from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.logging import set_log_level
from netqasm.subroutine import (
    Subroutine,
    Command,
    # Register,
    # Address,
    # ArrayEntry,
    # ArraySlice,
)
from netqasm.encoding import RegisterName
from netqasm.instructions import Instruction
from netqasm.parsing import parse_binary_subroutine
from netqasm.network_stack import CREATE_FIELDS, OK_FIELDS

from netqasm import instr2
from netqasm.instr2.operand import (
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
    subroutine = parse_binary_subroutine(alice.storage[1].msg)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
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
        instr2.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            value=Immediate(1),
        ),
        instr2.core.QAllocInstruction(
            qreg=Register(RegisterName.Q, 0),
        ),
        instr2.core.InitInstruction(
            qreg=Register(RegisterName.Q, 0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            value=Immediate(0),
        ),
        instr2.vanilla.GateHInstruction(
            qreg=Register(RegisterName.Q, 0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            value=Immediate(1),
        ),
        instr2.vanilla.GateXInstruction(
            qreg=Register(RegisterName.Q, 0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            value=Immediate(0),
        ),
        instr2.vanilla.GateXInstruction(
            qreg=Register(RegisterName.Q, 0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            value=Immediate(1),
        ),
        instr2.vanilla.GateHInstruction(
            qreg=Register(RegisterName.Q, 0),
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
    subroutine = parse_binary_subroutine(alice.storage[1].msg)
    expected = Subroutine(netqasm_version=(0, 0), app_id=0, commands=[
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
        instr2.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            value=Immediate(0),
        ),
        instr2.vanilla.RotXInstruction(
            qreg=Register(RegisterName.Q, 0),
            angle_num=Immediate(1),
            angle_denom=Immediate(1),
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
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(OK_FIELDS),
        ),
        instr2.core.ArrayInstruction(
            size=Register(RegisterName.R, 0),
            address=Address(0),
        ),
        # Qubit address array
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(1),
        ),
        instr2.core.ArrayInstruction(
            size=Register(RegisterName.R, 0),
            address=Address(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(0),
        ),
        instr2.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(1, index=Register(RegisterName.R, 1)),
        ),
        # ent info array
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(CREATE_FIELDS),
        ),
        instr2.core.ArrayInstruction(
            size=Register(RegisterName.R, 0),
            address=Address(2),
        ),
        # tp arg
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(0),
        ),
        instr2.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ),
        # num pairs arg
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(1),
        ),
        instr2.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ),
        # create cmd
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            value=Immediate(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 3),
            value=Immediate(2),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 4),
            value=Immediate(0),
        ),
        instr2.core.CreateEPRInstruction(
            remote_node_id=Register(RegisterName.R, 0),
            epr_socket_id=Register(RegisterName.R, 1),
            qubit_addr_array=Register(RegisterName.R, 2),
            arg_array=Register(RegisterName.R, 3),
            ent_info_array=Register(RegisterName.R, 4),
        ),
        # wait cmd
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(OK_FIELDS),
        ),
        instr2.core.WaitAllInstruction(
            slice=ArraySlice(
                address=Address(0),
                start=Register(RegisterName.R, 0),
                stop=Register(RegisterName.R, 1),
            ),
        ),
        # Hadamard
        instr2.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            value=Immediate(0),
        ),
        instr2.vanilla.GateHInstruction(
            qreg=Register(RegisterName.Q, 0),
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
        instr2.core.RetArrInstruction(
            address=Address(0),
        ),
        instr2.core.RetArrInstruction(
            address=Address(1),
        ),
        instr2.core.RetArrInstruction(
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
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(2 * OK_FIELDS),
        ),
        instr2.core.ArrayInstruction(
            size=Register(RegisterName.R, 0),
            address=Address(0),
        ),
        # Qubit address array
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(2),
        ),
        instr2.core.ArrayInstruction(
            size=Register(RegisterName.R, 0),
            address=Address(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(0),
        ),
        instr2.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(1, index=Register(RegisterName.R, 1)),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(1),
        ),
        instr2.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(1, index=Register(RegisterName.R, 1)),
        ),
        # ent info array
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(CREATE_FIELDS),
        ),
        instr2.core.ArrayInstruction(
            size=Register(RegisterName.R, 0),
            address=Address(2),
        ),
        # tp arg
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(0),
        ),
        instr2.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ),
        # num pairs arg
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(2),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(1),
        ),
        instr2.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(2, index=Register(RegisterName.R, 1)),
        ),
        # create cmd
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            value=Immediate(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 3),
            value=Immediate(2),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 4),
            value=Immediate(0),
        ),
        instr2.core.CreateEPRInstruction(
            remote_node_id=Register(RegisterName.R, 0),
            epr_socket_id=Register(RegisterName.R, 1),
            qubit_addr_array=Register(RegisterName.R, 2),
            arg_array=Register(RegisterName.R, 3),
            ent_info_array=Register(RegisterName.R, 4),
        ),
        # wait cmd
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 0),
            value=Immediate(0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(2 * OK_FIELDS),
        ),
        instr2.core.WaitAllInstruction(
            slice=ArraySlice(
                address=Address(0),
                start=Register(RegisterName.R, 0),
                stop=Register(RegisterName.R, 1),
            ),
        ),
        # Hadamards
        instr2.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            value=Immediate(0),
        ),
        instr2.vanilla.GateHInstruction(
            qreg=Register(RegisterName.Q, 0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.Q, 0),
            value=Immediate(1),
        ),
        instr2.vanilla.GateHInstruction(
            qreg=Register(RegisterName.Q, 0),
        ),
        # return cmds
        instr2.core.RetArrInstruction(
            address=Address(0),
        ),
        instr2.core.RetArrInstruction(
            address=Address(1),
        ),
        instr2.core.RetArrInstruction(
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
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(OK_FIELDS),
        ),
        instr2.core.ArrayInstruction(
            size=Register(RegisterName.R, 1),
            address=Address(0),
        ),
        # ent info array
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(CREATE_FIELDS),
        ),
        instr2.core.ArrayInstruction(
            size=Register(RegisterName.R, 1),
            address=Address(1),
        ),
        # tp arg
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            value=Immediate(0),
        ),
        instr2.core.StoreInstruction(
            reg=Register(RegisterName.R, 1),
            entry=ArrayEntry(1, index=Register(RegisterName.R, 2)),
        ),
        # num pairs arg
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            value=Immediate(1),
        ),
        instr2.core.StoreInstruction(
            reg=Register(RegisterName.R, 1),
            entry=ArrayEntry(1, index=Register(RegisterName.R, 2)),
        ),
        # create cmd
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            value=Immediate(0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 3),
            value=Immediate(1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 4),
            value=Immediate(0),
        ),
        instr2.core.CreateEPRInstruction(
            remote_node_id=Register(RegisterName.R, 1),
            epr_socket_id=Register(RegisterName.R, 2),
            qubit_addr_array=Register(RegisterName.C, 0),
            arg_array=Register(RegisterName.R, 3),
            ent_info_array=Register(RegisterName.R, 4),
        ),
        # wait cmd
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(0),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 2),
            value=Immediate(OK_FIELDS),
        ),
        instr2.core.WaitAllInstruction(
            slice=ArraySlice(
                address=Address(0),
                start=Register(RegisterName.R, 1),
                stop=Register(RegisterName.R, 2),
            ),
        ),
        # if statement
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(2),
        ),
        instr2.core.LoadInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(
                address=Address(0),
                index=Register(RegisterName.R, 1),
            ),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(0),
        ),
        instr2.core.BneInstruction(
            reg0=Register(RegisterName.R, 0),
            reg1=Register(RegisterName.R, 1),
            line=Immediate(28),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(2),
        ),
        instr2.core.LoadInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(
                address=Address(0),
                index=Register(RegisterName.R, 1),
            ),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(1),
        ),
        instr2.core.AddInstruction(
            regout=Register(RegisterName.R, 0),
            reg0=Register(RegisterName.R, 0),
            reg1=Register(RegisterName.R, 1),
        ),
        instr2.core.SetInstruction(
            reg=Register(RegisterName.R, 1),
            value=Immediate(2),
        ),
        instr2.core.StoreInstruction(
            reg=Register(RegisterName.R, 0),
            entry=ArrayEntry(
                address=Address(0),
                index=Register(RegisterName.R, 1),
            ),
        ),
        # return cmds
        instr2.core.RetArrInstruction(
            address=Address(0),
        ),
        instr2.core.RetArrInstruction(
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
