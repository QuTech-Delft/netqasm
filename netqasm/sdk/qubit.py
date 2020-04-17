from cqc.pythonLib import qubit
from cqc.cqcHeader import CQC_CMD_NEW, CQC_CMD_MEASURE

from netqasm.sdk.meas_outcome import MeasurementOutcome


class Qubit(qubit):
    def __init__(self, conn, put_new_command=True, ent_info=None):
        self._conn = conn
        self._qID = self._conn.new_qubitID()
        # NOTE this is needed to be compatible with CQC abstract class
        self.notify = False

        if put_new_command:
            self._conn.put_command(self._qID, CQC_CMD_NEW)

        self._active = None
        self._set_active(True)

        self._ent_info = ent_info

        self._remote_ent_node = None

    @property
    def _conn(self):
        # The attribute _cqc is used for backwards compatibility
        return self._cqc

    @_conn.setter
    def _conn(self, value):
        self._cqc = value

    def measure(self, var_name=None, inplace=False):
        self.check_active()

        if var_name is None:
            var_name = self._conn._get_unused_variable(start_with="m")
        address_index = self._conn._create_new_outcome_variable(var_name=var_name)

        self._conn.put_command(self._qID, CQC_CMD_MEASURE, address_index=address_index, inplace=inplace)

        if not inplace:
            self._set_active(False)

        return MeasurementOutcome(
            connection=self._conn,
            var_name=var_name,
        )

    @property
    def entanglement_info(self):
        return self._ent_info

    @property
    def remote_entangled_node(self):
        if self._remote_entNode is not None:
            return self._remote_ent_node
        if self.entanglement_info is None:
            return None
        # Lookup remote entangled node
        remote_node_id = self.entanglement_info.remote_node_id
        remote_node_name = self._conn._get_remote_node_name(remote_node_id)
        self._remote_ent_node = remote_node_name
        return remote_node_name
