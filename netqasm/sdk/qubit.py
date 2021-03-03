"""TODO write about qubits"""
from __future__ import annotations
from typing import Optional, Union
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from netqasm.sdk.connection import BaseNetQASMConnection
    from qlink_interface import LinkLayerOKTypeK

from netqasm.lang.instr.instr_enum import Instruction
from netqasm.sdk.futures import RegFuture, Future


class QubitNotActiveError(MemoryError):
    pass


class Qubit:
    def __init__(
        self,
        conn: BaseNetQASMConnection,
        add_new_command: bool = True,
        ent_info: Optional[LinkLayerOKTypeK] = None,
        virtual_address: Optional[int] = None
    ):
        self._conn: BaseNetQASMConnection = conn
        if virtual_address is None:
            self._qubit_id: int = self._conn.new_qubit_id()
        else:
            self._qubit_id = virtual_address

        if add_new_command:
            self._conn.add_new_qubit_commands(qubit_id=self.qubit_id)

        self._active: bool = False
        self._activate()

        self._ent_info: Optional[LinkLayerOKTypeK] = ent_info

        self._remote_ent_node: Optional[str] = None

    def __str__(self) -> str:
        if self.active:
            return "Qubit at the node {}".format(self._conn.node_name)
        else:
            return "Not active qubit"

    @property
    def connection(self) -> BaseNetQASMConnection:
        """Get the NetQASM connection of this qubit"""
        return self._conn

    @property
    def qubit_id(self) -> int:
        """Get the qubit ID"""
        return self._qubit_id

    @qubit_id.setter
    def qubit_id(self, qubit_id: int) -> None:
        assert isinstance(qubit_id, int), "qubit_id should be an int"
        self._qubit_id = qubit_id

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, active: bool) -> None:
        assert isinstance(active, bool), "active shoud be a bool"

        # Check if not already new state
        if self._active == active:
            return

        self._active = active

        if active:
            self._activate()
        else:
            self._deactivate()

    def _activate(self) -> None:
        self._active = True
        if self not in self._conn.active_qubits:
            self._conn.active_qubits.append(self)

    def _deactivate(self) -> None:
        self._active = False
        if self in self._conn.active_qubits:
            self._conn.active_qubits.remove(self)

    @property
    def entanglement_info(self) -> Optional[LinkLayerOKTypeK]:
        """Get the entanglement info"""
        return self._ent_info

    @property
    def remote_entangled_node(self) -> Optional[str]:
        """Get the name of the remote node the qubit is entangled with.
        If not entanled, `None` is returned.
        """
        if self._remote_ent_node is not None:
            return self._remote_ent_node
        if self.entanglement_info is None:
            return None
        # Lookup remote entangled node
        remote_node_id = self.entanglement_info.remote_node_id
        remote_node_name = self._conn.network_info._get_node_name(node_id=remote_node_id)
        self._remote_ent_node = remote_node_name
        return remote_node_name

    def assert_active(self) -> None:
        """
        Checks if the qubit is active
        """
        if not self.active:
            raise QubitNotActiveError(f"Qubit {self.qubit_id} is not active")

    def measure(
        self,
        future: Optional[Union[Future, RegFuture]] = None,
        inplace: bool = False,
        store_array: bool = True,
    ) -> Union[Future, RegFuture]:
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

    def X(self) -> None:
        """
        Performs a X on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.X, qubit_id=self.qubit_id)

    def Y(self) -> None:
        """
        Performs a Y on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.Y, qubit_id=self.qubit_id)

    def Z(self) -> None:
        """
        Performs a Z on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.Z, qubit_id=self.qubit_id)

    def T(self) -> None:
        """
        Performs a T gate on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.T, qubit_id=self.qubit_id)

    def H(self) -> None:
        """
        Performs a Hadamard on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.H, qubit_id=self.qubit_id)

    def K(self) -> None:
        """
        Performs a K gate on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.K, qubit_id=self.qubit_id)

    def S(self) -> None:
        """
        Performs a S gate on the qubit.
        """
        self._conn.add_single_qubit_commands(instr=Instruction.S, qubit_id=self.qubit_id)

    def rot_X(self, n: int = 0, d: int = 0, angle: Optional[float] = None):
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

    def rot_Y(self, n: int = 0, d: int = 0, angle: Optional[float] = None):
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

    def rot_Z(self, n: int = 0, d: int = 0, angle: Optional[float] = None):
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

    def cnot(self, target: Qubit) -> None:
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

    def cphase(self, target: Qubit) -> None:
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

    def reset(self) -> None:
        r"""
        Resets the qubit to the state \|0>
        """
        self._conn.add_init_qubit_commands(qubit_id=self.qubit_id)

    def free(self) -> None:
        """
        Unallocates the qubit.
        """
        self._conn.add_qfree_commands(qubit_id=self.qubit_id)


class _FutureQubit(Qubit):
    def __init__(self, conn: BaseNetQASMConnection, future_id: Future):
        """Used by NetQASMConnection to handle operations on a future qubit (e.g. post createEPR)"""
        self._conn: BaseNetQASMConnection = conn

        self.qubit_id: Future = future_id

        self._activate()

    @property
    def entanglement_info(self) -> Optional[LinkLayerOKTypeK]:
        raise NotImplementedError("Cannot access entanglement info of a future qubit yet")

    @property
    def remote_entangled_node(self) -> Optional[str]:
        raise NotImplementedError("Cannot access entanglement info of a future qubit yet")
