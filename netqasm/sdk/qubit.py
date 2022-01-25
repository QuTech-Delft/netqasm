"""Qubit representation.

This module contains the `Qubit` class, which are used by application scripts
as handles to in-memory qubits.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from netqasm.lang.ir import GenericInstr
from netqasm.sdk.futures import Future, RegFuture

if TYPE_CHECKING:
    from netqasm import qlink_compat
    from netqasm.sdk import connection as sdkconn
    from netqasm.sdk.builder import Builder


class QubitNotActiveError(MemoryError):
    pass


class Qubit:
    """Representation of a qubit that has been allocated in the quantum node.

    A `Qubit` instance represents a quantum state that is stored in a physical qubit
    somewhere in the quantum node.
    The particular qubit is identified by its virtual qubit ID.
    To which physical qubit ID this is mapped (at a given time), is handled completely
    by the quantum node controller and is not known to the `Qubit` itself.

    A `Qubit` object can be instantiated in an application script.
    Such an instantiation is automatically compiled into NetQASM instructions that
    allocate and initialize a new qubit in the quantum node controller.

    A `Qubit` object may also be obtained by SDK functions that return them, like
    the `create()` method on an `EPRSocket`, which returns the object as a handle to
    the qubit that is now entangled with one in another node.

    Qubit operations like applying gates and measuring them are done by calling
    methods on a `Qubit` instance.
    """

    def __init__(
        self,
        conn: sdkconn.BaseNetQASMConnection,
        add_new_command: bool = True,
        ent_info: Optional[qlink_compat.LinkLayerOKTypeK] = None,
        virtual_address: Optional[int] = None,
    ):
        """Qubit constructor. This is the standard way to allocate a new qubit in
        an application.

        :param conn: connection of the application in which to allocate the qubit
        :param add_new_command: whether to automatically add NetQASM instructions to
            the current subroutine to allocate and initialize the qubit
        :param ent_info: entanglement generation information in case this qubit is
            the result of an entanglement generation request
        :param virtual_address: explicit virtual ID to use for this qubit. If None,
            a free ID is automatically chosen.
        """
        self._conn: sdkconn.BaseNetQASMConnection = conn
        if virtual_address is None:
            self._qubit_id: int = self.builder.new_qubit_id()
        else:
            self._qubit_id = virtual_address

        if add_new_command:
            self.builder._build_cmds_new_qubit(qubit_id=self.qubit_id)

        self._active: bool = False
        self._activate()

        self._ent_info: Optional[qlink_compat.LinkLayerOKTypeK] = ent_info

        self._remote_ent_node: Optional[str] = None

    def __str__(self) -> str:
        if self.active:
            return "Qubit at the node {}".format(self._conn.node_name)
        else:
            return "Not active qubit"

    @property
    def connection(self) -> sdkconn.BaseNetQASMConnection:
        """Get the NetQASM connection of this qubit"""
        return self._conn

    @property
    def builder(self) -> Builder:
        """Get the Builder of this qubit's connection"""
        return self.connection.builder

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
        if not self.builder._mem_mgr.is_qubit_active(self):
            self.builder._mem_mgr.activate_qubit(self)

    def _deactivate(self) -> None:
        self._active = False
        if self.builder._mem_mgr.is_qubit_active(self):
            self.builder._mem_mgr.deactivate_qubit(self)

    @property
    def entanglement_info(self) -> Optional[qlink_compat.LinkLayerOKTypeK]:
        """Get information about the successful link layer request that resulted in
        this qubit."""
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
        remote_node_name = self._conn.network_info._get_node_name(
            node_id=remote_node_id
        )
        self._remote_ent_node = remote_node_name
        return remote_node_name

    def assert_active(self) -> None:
        """Assert that the qubit is active, i.e. allocated."""
        if not self.active:
            raise QubitNotActiveError(f"Qubit {self.qubit_id} is not active")

    def measure(
        self,
        future: Optional[Union[Future, RegFuture]] = None,
        inplace: bool = False,
        store_array: bool = True,
    ) -> Union[Future, RegFuture]:
        """Measure the qubit in the standard basis and get the measurement outcome.

        :param future: the `Future` to place the outcome in. If None, a Future is
            created automatically.
        :param inplace: If False, the measurement is destructive and the qubit is
            removed from memory. If True, the qubit is left in the post-measurement
            state.
        :param store_array: whether to store the outcome in an array. If not, it is
            placed in a register. Only used if `future` is None.
        :return: the Future representing the measurement outcome. It is a `Future` if
        the result is in an array (default) or `RegFuture` if the result is in a
        register.
        """
        self.assert_active()

        if future is None:
            if store_array:
                array = self.builder.alloc_array(1)
                future = array.get_future_index(0)
            else:
                future = RegFuture(self._conn)

        self.builder._build_cmds_measure(
            qubit_id=self.qubit_id,
            future=future,
            inplace=inplace,
        )

        if not inplace:
            self.active = False

        return future

    def X(self) -> None:
        """Apply an X gate on the qubit."""
        self.builder._build_cmds_single_qubit(
            instr=GenericInstr.X, qubit_id=self.qubit_id
        )

    def Y(self) -> None:
        """Apply a Y gate on the qubit."""
        self.builder._build_cmds_single_qubit(
            instr=GenericInstr.Y, qubit_id=self.qubit_id
        )

    def Z(self) -> None:
        """Apply a Z gate on the qubit."""
        self.builder._build_cmds_single_qubit(
            instr=GenericInstr.Z, qubit_id=self.qubit_id
        )

    def T(self) -> None:
        """Apply a T gate on the qubit.

        A T gate is a Z-rotation with angle pi/4.
        """
        self.builder._build_cmds_single_qubit(
            instr=GenericInstr.T, qubit_id=self.qubit_id
        )

    def H(self) -> None:
        """Apply a Hadamard gate on the qubit."""
        self.builder._build_cmds_single_qubit(
            instr=GenericInstr.H, qubit_id=self.qubit_id
        )

    def K(self) -> None:
        """Apply a K gate on the qubit.

        A K gate moves the |0> state to +|i> (positive Y) and vice versa.
        """
        self.builder._build_cmds_single_qubit(
            instr=GenericInstr.K, qubit_id=self.qubit_id
        )

    def S(self) -> None:
        """Apply an S gate on the qubit.

        An S gate is a Z-rotation with angle pi/2.
        """
        self.builder._build_cmds_single_qubit(
            instr=GenericInstr.S, qubit_id=self.qubit_id
        )

    def rot_X(self, n: int = 0, d: int = 0, angle: Optional[float] = None):
        """Do a rotation around the X-axis of the specified angle.

        The angle is interpreted as ǹ * pi / 2 ^d` radians.
        For example, (n, d) = (1, 2) represents an angle of pi/4 radians.
        If `angle` is specified, `n` and `d` are ignored and this instruction is
        automatically converted into a sequence of (n, d) rotations such that the
        discrete (n, d) values approximate the original angle.

        :param n: numerator of discrete angle specification
        :param d: denomerator of discrete angle specification
        :param angle: exact floating-point angle, defaults to None
        """
        self.builder._build_cmds_single_qubit_rotation(
            instruction=GenericInstr.ROT_X,
            virtual_qubit_id=self.qubit_id,
            n=n,
            d=d,
            angle=angle,
        )

    def rot_Y(self, n: int = 0, d: int = 0, angle: Optional[float] = None):
        """Do a rotation around the Y-axis of the specified angle.

        The angle is interpreted as ǹ * pi / 2 ^d` radians.
        For example, (n, d) = (1, 2) represents an angle of pi/4 radians.
        If `angle` is specified, `n` and `d` are ignored and this instruction is
        automatically converted into a sequence of (n, d) rotations such that the
        discrete (n, d) values approximate the original angle.

        :param n: numerator of discrete angle specification
        :param d: denomerator of discrete angle specification
        :param angle: exact floating-point angle, defaults to None
        """
        self.builder._build_cmds_single_qubit_rotation(
            instruction=GenericInstr.ROT_Y,
            virtual_qubit_id=self.qubit_id,
            n=n,
            d=d,
            angle=angle,
        )

    def rot_Z(self, n: int = 0, d: int = 0, angle: Optional[float] = None):
        """Do a rotation around the Z-axis of the specified angle.

        The angle is interpreted as ǹ * pi / 2 ^d` radians.
        For example, (n, d) = (1, 2) represents an angle of pi/4 radians.
        If `angle` is specified, `n` and `d` are ignored and this instruction is
        automatically converted into a sequence of (n, d) rotations such that the
        discrete (n, d) values approximate the original angle.

        :param n: numerator of discrete angle specification
        :param d: denomerator of discrete angle specification
        :param angle: exact floating-point angle, defaults to None
        """
        self.builder._build_cmds_single_qubit_rotation(
            instruction=GenericInstr.ROT_Z,
            virtual_qubit_id=self.qubit_id,
            n=n,
            d=d,
            angle=angle,
        )

    def cnot(self, target: Qubit) -> None:
        """Apply a CNOT gate between this qubit (control) and a target qubit.

        :param target: target qubit. Should have the same connection as this qubit.
        """
        self.builder._build_cmds_two_qubit(
            instr=GenericInstr.CNOT,
            control_qubit_id=self.qubit_id,
            target_qubit_id=target.qubit_id,
        )

    def cphase(self, target: Qubit) -> None:
        """Apply a CPHASE (CZ) gate between this qubit (control) and a target qubit.

        :param target: target qubit. Should have the same connection as this qubit.
        """
        self.builder._build_cmds_two_qubit(
            instr=GenericInstr.CPHASE,
            control_qubit_id=self.qubit_id,
            target_qubit_id=target.qubit_id,
        )

    def reset(self) -> None:
        r"""Reset the qubit to the state \|0>."""
        self.builder._build_cmds_init_qubit(qubit_id=self.qubit_id)

    def free(self) -> None:
        """
        Free the qubit and its virtual ID.

        After freeing, the underlying physical qubit can be used to store another state.
        """
        self.builder._build_cmds_qfree(qubit_id=self.qubit_id)


class FutureQubit(Qubit):
    """A Qubit that will be available in the future.

    This class is very similar to the `Future` class which is used for classical
    values.
    A `FutureQubit` acts like a `Qubit` so that all qubit operations can be applied on
    it. FutureQubits are typically the result of EPR creating requests, where they
    represent the qubits that will be available when EPR generation has finished.
    """

    def __init__(self, conn: sdkconn.BaseNetQASMConnection, future_id: Future):
        """FutureQubit constructor. Typically not used directly.

        :param conn: connection through which subroutines are sent that contain this
            qubit
        :param future_id: the virtual ID this qubit will have
        """
        self._conn: sdkconn.BaseNetQASMConnection = conn

        self.qubit_id: Future = future_id

        self._activate()

    @property
    def entanglement_info(self) -> Optional[qlink_compat.LinkLayerOKTypeK]:
        raise NotImplementedError(
            "Cannot access entanglement info of a future qubit yet"
        )

    @property
    def remote_entangled_node(self) -> Optional[str]:
        raise NotImplementedError(
            "Cannot access entanglement info of a future qubit yet"
        )
