import logging

from netqasm.sdk.connection import NetQASMConnection
from netqasm.sdk.qubit import Qubit
from netqasm.parser import Subroutine, Command, QubitAddress

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
    subroutine = storage[0]
    expected = Subroutine(netqasm_version='0.0', app_id=0, commands=[
        Command(instruction="qalloc", args=[], operands=[
            QubitAddress(0),
        ]),
        Command(instruction="init", args=[], operands=[
            QubitAddress(0),
        ]),
        Command(instruction="qalloc", args=[], operands=[
            QubitAddress(1),
        ]),
        Command(instruction="init", args=[], operands=[
            QubitAddress(1),
        ]),
        Command(instruction="h", args=[], operands=[
            QubitAddress(0),
        ]),
        Command(instruction="x", args=[], operands=[
            QubitAddress(1),
        ]),
        Command(instruction="x", args=[], operands=[
            QubitAddress(0),
        ]),
        Command(instruction="h", args=[], operands=[
            QubitAddress(1),
        ]),
        Command(instruction="qfree", args=[], operands=[
            QubitAddress(0),
        ]),
        Command(instruction="qfree", args=[], operands=[
            QubitAddress(1),
        ]),
    ])
    print(subroutine)
    print(expected)
    assert subroutine == expected
