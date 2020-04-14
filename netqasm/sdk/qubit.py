from cqc.pythonLib import qubit
from cqc.cqcHeader import CQC_CMD_NEW, CQC_CMD_MEASURE
from netqasm.sdk.meas_outcome import MeasurementOutcome


class Qubit(qubit):
    def __init__(self, conn, put_new_command=True):
        self._conn = conn
        self._qID = self._conn.new_qubitID()
        # NOTE this is needed to be compatible with CQC abstract class
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

    def measure(self, var_name=None):
        self.check_active()

        if var_name is None:
            array_entry = None
        else:
            array_entry = self._conn._create_new_outcome_variable(var_name=var_name)

        self._conn.put_command(self._qID, CQC_CMD_MEASURE, array_entry=array_entry)

        self._set_active(False)

        return MeasurementOutcome(
            connection=self,
            var_name=var_name,
        )
