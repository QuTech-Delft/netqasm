from cqc.pythonLib import qubit
from cqc.cqcHeader import CQC_CMD_NEW, CQC_CMD_MEASURE

from netqasm.instructions import Instruction


class Qubit(qubit):
    def __init__(self, conn, put_new_command=True, ent_info=None, virtual_address=None):
        self._conn = conn
        if virtual_address is None:
            self._qID = self._conn.new_qubitID()
        else:
            self._qID = virtual_address
        # NOTE this is needed to be compatible with CQC abstract class
        self.notify = False

        if put_new_command:
            self._conn.put_command(CQC_CMD_NEW, qID=self._qID)

        # TODO fix this after moving from cqc
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

    def measure(self, future=None, inplace=False):
        self.check_active()

        if future is None:
            array = self._conn.new_array(1)
            future = array.get_future_index(0)

        self._conn.put_command(CQC_CMD_MEASURE, qID=self._qID, future=future, inplace=inplace)

        if not inplace:
            self._set_active(False)

        return future

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

    def rot_x(self, n=0, d=1):
        """Performs a rotation around the X-axis of an angle `n * pi / d`"""
        self._conn._single_qubit_rotation(
            instruction=Instruction.ROT_X,
            virtual_qubit_id=self._qID,
            n=n,
            d=d,
        )

    def rot_y(self, n=0, d=1):
        """Performs a rotation around the Y-axis of an angle `n * pi / d`"""
        self._conn._single_qubit_rotation(
            instruction=Instruction.ROT_Y,
            virtual_qubit_id=self._qID,
            n=n,
            d=d,
        )

    def rot_z(self, n=0, d=1):
        """Performs a rotation around the Z-axis of an angle `n * pi / d`"""
        self._conn._single_qubit_rotation(
            instruction=Instruction.ROT_Z,
            virtual_qubit_id=self._qID,
            n=n,
            d=d,
        )


class _FutureQubit(Qubit):
    def __init__(self, conn, future_id):
        """Used by NetQASMConnection to handle operations on a future qubit (e.g. post createEPR)"""
        self._conn = conn
        # NOTE this is needed to be compatible with CQC abstract class
        self.notify = False

        self._qID = future_id

        # TODO fix this after moving from cqc
        self._active = None
        self._set_active(True)

    @property
    def entanglement_info(self):
        raise NotImplementedError("Cannot access entanglement info of a future qubit yet")

    @property
    def remote_entangled_node(self):
        raise NotImplementedError("Cannot access entanglement info of a future qubit yet")

    def _set_active(self, be_active):
        # TODO when changing the status of a future qubit, how to treat the status of the actual qubit?
        self._active = be_active
