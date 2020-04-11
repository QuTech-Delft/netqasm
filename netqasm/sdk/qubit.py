from cqc.pythonLib import qubit
from cqc.cqcHeader import CQC_CMD_NEW, CQC_CMD_MEASURE
from netqasm.sdk.meas_outcome import MeasurementOutcome
from netqasm.sdk.shared_memory import get_shared_memory


class Qubit(qubit):
    def __init__(self, conn, put_new_command=True):
        self._conn = conn
        self._qID = self._conn.new_qubitID()
        # TODO this is needed to be backwards compatible
        self.notify = False

        if put_new_command:
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

    def measure(self, outcome_reg=None):
        self.check_active()

        if outcome_reg is None:
            outcome_reg = self._conn._get_new_meas_outcome_reg()
        self._conn.put_command(self._qID, CQC_CMD_MEASURE, outcome_reg=outcome_reg)

        self._set_active(False)

        # TODO update how this is treated
        memory = get_shared_memory(
            node_name=self._conn.name,
            key=self._conn._appID,
        )
        return MeasurementOutcome(
            memory=memory,
            address=outcome_reg,
        )
