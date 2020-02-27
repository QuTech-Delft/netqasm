import logging

from cqc.pythonLib import qubit
from cqc.cqcHeader import CQC_CMD_NEW, CQC_CMD_MEASURE
from netqasm.parser import Subroutine
from .meas_outcome import MeasurementOutcome
from .shared_memory import get_shared_memory


class Qubit(qubit):
    def __init__(self, conn):
        self._conn = conn
        self._qID = self._conn.new_qubitID()
        # TODO this is needed to be backwards compatible
        self.notify = False

        self._conn.put_command(self._qID, CQC_CMD_NEW)

        self._active = None
        self._set_active(True)

    @property
    def _conn(self):
        # The attribute _cqc is used for backwards compatibility
        return self._cqc

    @_conn.setter
    def _conn(self, value):
        self._cqc = value

    def measure(self, outcome_address=None):
        self.check_active()

        if outcome_address is None:
            outcome_address = self._conn._get_new_classical_address()
        self._conn.put_command(self._qID, CQC_CMD_MEASURE, outcome_address=outcome_address)

        self._set_active(False)

        memory = get_shared_memory(
            node_name=self._conn.name,
            key=self._conn._appID,
        )
        return MeasurementOutcome(
            memory=memory,
            address=outcome_address,
        )


# TODO tests
from .connection import NetQASMConnection

storage = []


class DebugConnection(NetQASMConnection):
    def commit(self, subroutine):
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
    expected = Subroutine(netqasm_version='0.0', app_id='0', instructions=[
        "qreg(2) @0",
        "init @0[0]",
        "init @0[1]",
        "h @0[0]",
        "x @0[1]",
        "x @0[0]",
        "h @0[1]",
    ])
    assert subroutine == expected


if __name__ == '__main__':
    test()
