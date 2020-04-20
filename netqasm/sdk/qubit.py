from cqc.pythonLib import qubit
from cqc.cqcHeader import CQC_CMD_NEW, CQC_CMD_MEASURE

from netqasm.sdk.futures import Array, Future
from netqasm.parsing import parse_register


class Qubit(qubit):
    def __init__(self, conn, put_new_command=True, ent_info=None):
        self._conn = conn
        self._qID = self._conn.new_qubitID()
        # NOTE this is needed to be compatible with CQC abstract class
        self.notify = False

        if put_new_command:
            self._conn.put_command(CQC_CMD_NEW, qID=self._qID)

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

    def measure(self, array=None, index=None, inplace=False):
        self.check_active()

        if array is None:
            array = self._conn.new_array(1)
            index = 0

        # TODO
        # if array is not None:
        if not isinstance(array, Array):
            raise TypeError(f"expected Array not {type(array)}")
        address = array.address
        if index is None:
            raise ValueError("If array is specified so must index be")
        if isinstance(index, int):
            pass
        elif isinstance(index, str):
            index = parse_register(index)
        else:
            raise TypeError("index should be int or str, not {type(index)}")
        # TODO
        # else:
        #     address = None
        #     index = None
            # var_name = self._conn._get_unused_variable(start_with="m")
        # address_index = self._conn._create_new_outcome_variable(var_name=var_name)

        self._conn.put_command(CQC_CMD_MEASURE, qID=self._qID, address=address, index=index, inplace=inplace)

        if not inplace:
            self._set_active(False)

        return Future(
            connection=self._conn,
            address=address,
            index=index,
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
