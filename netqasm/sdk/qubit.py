"""TODO write about qubits"""

from netqasm.lang.instr.instr_enum import Instruction
from netqasm.sdk.futures import RegFuture


class QubitNotActiveError(MemoryError):
    pass


class Qubit:
    def __init__(self, conn, add_new_command=True, ent_info=None, virtual_address=None):
        self._conn = conn
        if virtual_address is None:
            self._qubit_id = self._conn.new_qubit_id()
        else:
            self._qubit_id = virtual_address

        if add_new_command:
            self._conn.add_new_qubit_commands(qubit_id=self.qubit_id)

        self._activate()

        self._ent_info = ent_info

        self._remote_ent_node = None

    def __str__(self):
        if self.active:
            return "Qubit at the node {}".format(self._conn.name)
        else:
            return "Not active qubit"

    @property
    def connection(self):
        """Get the NetQASM connection of this qubit"""
        return self._conn

    @property
    def qubit_id(self):
        """Get the qubit ID"""
        return self._qubit_id

    @qubit_id.setter
    def qubit_id(self, qubit_id):
        assert isinstance(qubit_id, int), "qubit_id should be an int"
        self._qubit_id = qubit_id

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, active):
        assert isinstance(active, bool), "active shoud be a bool"

        # Check if not already new state
        if self._active == active:
            return

        self._active = active

        if active:
            self._activate()
        else:
            self._deactivate()

    def _activate(self):
        self._active = True
        if self not in self._conn.active_qubits:
            self._conn.active_qubits.append(self)

    def _deactivate(self):
        self._active = False
        if self in self._conn.active_qubits:
            self._conn.active_qubits.remove(self)

    @property
    def entanglement_info(self):
        """Get the entanglement info"""
        return self._ent_info

    @property
    def remote_entangled_node(self):
        """Get the name of the remote node the qubit is entangled with.
        If not entanled, `None` is returned.
        """
        if self._remote_ent_node is not None:
            return self._remote_ent_node
        if self.entanglement_info is None:
            return None
        # Lookup remote entangled node
        remote_node_id = self.entanglement_info.remote_node_id
        remote_node_name = self._conn._get_node_name(node_id=remote_node_id)
        self._remote_ent_node = remote_node_name
        return remote_node_name

    def assert_active(self):
        """
        Checks if the qubit is active
        """
        if not self.active:
            raise QubitNotActiveError(f"Qubit {self.qubit_id} is not active")

    def measure(self, future=None, inplace=False, store_array=True):
        """
        Measures the qubit in the standard basis and returns the measurement outcome.

        Parameters
        ----------
        future : :class:`~.sdk.futures.Future`
            The future to place the outcome in
        inplace : bool
            If inplace=False, the measurement is destructive and the qubit is removed from memory.
            If inplace=True, the qubit is left in the post-measurement state.
        """
        self.assert_active()

        if future is None:
            if store_array:
                array = self._conn.new_array(1)
                future = array.get_future_index(0)
            else:
                future = RegFuture(self._conn)

        self._conn.add_measure_commands(
            qubit_id=self.qubit_id,
            future=future,
            inplace=inplace,
        )

        if not inplace:
            self.active = False

        return future

    def X(self):
        """
        Performs a X on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.X, qubit_id=self.qubit_id)

    def Y(self):
        """
        Performs a Y on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.Y, qubit_id=self.qubit_id)

    def Z(self):
        """
        Performs a Z on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.Z, qubit_id=self.qubit_id)

    def T(self):
        """
        Performs a T gate on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.T, qubit_id=self.qubit_id)

    def H(self):
        """
        Performs a Hadamard on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.H, qubit_id=self.qubit_id)

    def K(self):
        """
        Performs a K gate on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.K, qubit_id=self.qubit_id)

    def S(self):
        """
        Performs a S gate on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.S, qubit_id=self.qubit_id)

    def rot_X(self, n=0, d=0, angle=None):
        """Performs a rotation around the X-axis of an angle `n * pi / 2 ^ d`
        If `angle` is specified `n` and `d` are ignored and a sequence of `n` and `d` are used to approximate the angle.
        """
        self._conn.add_single_qubit_rotation_commands(
            instruction=Instruction.ROT_X,
            virtual_qubit_id=self.qubit_id,
            n=n,
            d=d,
            angle=angle,
        )

    def rot_Y(self, n=0, d=0, angle=None):
        """Performs a rotation around the Y-axis of an angle `n * pi / 2 ^ d`
        If `angle` is specified `n` and `d` are ignored and a sequence of `n` and `d` are used to approximate the angle.
        """
        self._conn.add_single_qubit_rotation_commands(
            instruction=Instruction.ROT_Y,
            virtual_qubit_id=self.qubit_id,
            n=n,
            d=d,
            angle=angle,
        )

    def rot_Z(self, n=0, d=0, angle=None):
        """Performs a rotation around the Z-axis of an angle `n * pi / 2 ^ d`
        If `angle` is specified `n` and `d` are ignored and a sequence of `n` and `d` are used to approximate the angle.
        """
        self._conn.add_single_qubit_rotation_commands(
            instruction=Instruction.ROT_Z,
            virtual_qubit_id=self.qubit_id,
            n=n,
            d=d,
            angle=angle,
        )

    def cnot(self, target):
        """
        Applies a cnot onto target.
        Target should be a qubit-object with the same connection.

        Parameters
        ----------
        target : :class:`~.Qubit`
            The target qubit
        """
        self._conn.add_two_qubit_commands(
            instr=Instruction.CNOT,
            control_qubit_id=self.qubit_id,
            target_qubit_id=target.qubit_id,
        )

    def cphase(self, target):
        """
        Applies a cphase onto target.
        Target should be a qubit-object with the same connection.

        Parameters
        ----------
        target : :class:`~.Qubit`
            The target qubit
        """
        self._conn.add_two_qubit_commands(
            instr=Instruction.CPHASE,
            control_qubit_id=self.qubit_id,
            target_qubit_id=target.qubit_id,
        )

    def reset(self):
        r"""
        Resets the qubit to the state \|0>
        """
        self._conn.add_init_qubit_command(qubit_id=self.qubit_id)

    def free(self):
        """
        Unallocates the qubit.
        """
        self._conn.add_qfree_commands(qubit_id=self.qubit_id)


class _FutureQubit(Qubit):
    def __init__(self, conn, future_id):
        """Used by NetQASMConnection to handle operations on a future qubit (e.g. post createEPR)"""
        self._conn = conn

        self.qubit_id = future_id

        self._activate()

    @property
    def entanglement_info(self):
        raise NotImplementedError("Cannot access entanglement info of a future qubit yet")

    @property
    def remote_entangled_node(self):
        raise NotImplementedError("Cannot access entanglement info of a future qubit yet")
