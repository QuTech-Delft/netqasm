"""EPR Socket interface."""

from __future__ import annotations

import abc
import logging
from contextlib import contextmanager
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable, ContextManager, List, Optional, Tuple, Union

from netqasm.logging.glob import get_netqasm_logger
from netqasm.qlink_compat import (
    EPRRole,
    EPRType,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerOKTypeR,
    RandomBasis,
    TimeUnit,
)
from netqasm.sdk.builder import EntRequestParams, EprKeepResult, EprMeasureResult
from netqasm.sdk.futures import RegFuture

from .qubit import FutureQubit, Qubit

if TYPE_CHECKING:
    from netqasm.sdk import connection

T_LinkLayerOkList = Union[
    List[LinkLayerOKTypeK], List[LinkLayerOKTypeM], List[LinkLayerOKTypeR]
]


class EPRMeasBasis(Enum):
    X = 0
    Y = auto()
    Z = auto()
    MX = auto()
    MY = auto()
    MZ = auto()


class EPRSocket(abc.ABC):
    """EPR socket class. Used to generate entanglement with a remote node.

    An EPR socket represents a connection with a single remote node through which
    EPR pairs can be generated. Its main interfaces are the `create` and `recv`
    methods. A typical use case for two nodes is that they both create an EPR socket
    to the other node, and during the protocol, one of the nodes does `create`
    operations on its socket while the other node does `recv` operations.

    A `create` operation asks the network stack to initiate generation of EPR pairs
    with the remote node. Depending on the type of generation, the result of this
    operation can be qubit objects or measurement outcomes.
    A `recv` operation asks the network stack to wait for the remote node to initiate
    generation of EPR pairs. Again, the result can be qubit objects or measurement
    outcomes.

    Each `create` operation on one node must be matched by a `recv` operation on the
    other node. Since "creating" and "receiving" must happen at the same time, a node
    that is doing a `create` operation on its socket cannot advance until the other
    node does the corresponding `recv`. This is different from classical network
    sockets where a "send" operation (roughly anologous to `create` in an EPR socket)
    does not block on the remote node receiving it.

    An EPR socket is identified by a triple consisting of (1) the remote node ID,
    (2) the local socket ID and (3) the remote socket ID.
    Two nodes that want to generate EPR pairs with each other should make sure that the
    IDs in their local sockets match.
    """

    def __init__(
        self,
        remote_app_name: str,
        epr_socket_id: int = 0,
        remote_epr_socket_id: int = 0,
        min_fidelity: int = 100,
    ):
        """Create an EPR socket. It still needs to be registered with the network
        stack separately.

        Registering and opening the EPR socket is currently done automatically by the
        connection that uses this EPR socket, specifically when a context is opened
        with that connection.

        :param remote_app_name: name of the remote party (i.e. the role, like "client",
            not necessarily the node name like "delft")
        :param epr_socket_id: local socket ID, defaults to 0
        :param remote_epr_socket_id: remote socket ID, defaults to 0. Note that this
            must match with the local socket ID of the remote node's EPR socket.
        :param min_fidelity: minimum desired fidelity for EPR pairs generated over this
            socket, in percentages (i.e. range 0-100). Defaults to 100.
        """
        self._conn: Optional[connection.BaseNetQASMConnection] = None
        self._remote_app_name: str = remote_app_name
        self._remote_node_id: Optional[
            int
        ] = None  # Gets set when the connection is set
        self._epr_socket_id: int = epr_socket_id
        self._remote_epr_socket_id: int = remote_epr_socket_id

        if (
            not isinstance(min_fidelity, int)
            or (min_fidelity < 0)
            or min_fidelity > 100
        ):
            raise ValueError(
                f"min_fidelity must be an integer in the range [0, 100], not {min_fidelity}"
            )
        self._min_fidelity: int = min_fidelity

        self._logger: logging.Logger = get_netqasm_logger(
            f"{self.__class__.__name__}({self._remote_app_name}, {self._epr_socket_id})"
        )

    @property
    def conn(self) -> connection.BaseNetQASMConnection:
        """Get the underlying :class:`NetQASMConnection`"""
        if self._conn is None:
            raise RuntimeError("EPRSocket does not have an open connection")
        return self._conn

    @conn.setter
    def conn(self, conn: connection.BaseNetQASMConnection):
        self._conn = conn
        self._remote_node_id = self._get_node_id(app_name=self._remote_app_name)

    @property
    def remote_app_name(self) -> str:
        """Get the remote application name"""
        return self._remote_app_name

    @property
    def remote_node_id(self) -> int:
        """Get the remote node ID"""
        if self._remote_node_id is None:
            raise RuntimeError("Remote Node ID has not been initialized")
        return self._remote_node_id

    @property
    def epr_socket_id(self) -> int:
        """Get the EPR socket ID"""
        return self._epr_socket_id

    @property
    def remote_epr_socket_id(self) -> int:
        """Get the remote EPR socket ID"""
        return self._remote_epr_socket_id

    @property
    def min_fidelity(self) -> int:
        """Get the desired minimum fidelity"""
        return self._min_fidelity

    def create_keep(
        self,
        number: int = 1,
        post_routine: Optional[Callable] = None,
        sequential: bool = False,
        time_unit: TimeUnit = TimeUnit.MICRO_SECONDS,
        max_time: int = 0,
        min_fidelity_all_at_end: Optional[int] = None,
        max_tries: Optional[int] = None,
    ) -> List[Qubit]:
        """Ask the network stack to generate EPR pairs with the remote node and keep
        them in memory.

        A `create_keep` operation must always be matched by a `recv_keep` operation on
        the remote node.

        If `sequential` is False (default), this operation returns a list of Qubit
        objects representing the local qubits that are each one half of the generated
        pairs. These qubits can then be manipulated locally just like locally
        initialized qubits, by e.g. applying gates or measuring them.
        Each qubit also contains information about the entanglement generation that
        lead to its creation, and can be accessed by its `entanglement_info` property.

        A typical example for just generating one pair with another node would be:

        .. code-block::

            q = epr_socket.create_keep()[0]
            # `q` can now be used as a normal qubit

        If `sequential` is False (default), the all requested EPR pairs are generated
        at once, before returning the results (qubits or entanglement info objects).

        If `sequential` is True, a callback function (`post_routine`) should be
        specified. After generating one EPR pair, this callback will be called, before
        generating the next pair. This method can e.g. be used to generate many EPR
        pairs (more than the number of physical qubits available), by measuring (and
        freeing up) each qubit before the next pair is generated.

        For example:

        .. code-block::

            outcomes = alice.new_array(num)

            def post_create(conn, q, pair):
                q.H()
                outcome = outcomes.get_future_index(pair)
                q.measure(outcome)
            epr_socket.create_keep(number=num, post_routine=post_create, sequential=True)


        :param number: number of EPR pairs to generate, defaults to 1
        :param post_routine: callback function for each genated pair. Only used if
            `sequential` is True.
            The callback should take three arguments `(conn, q, pair)` where
            * `conn` is the connection (e.g. `self`)
            * `q` is the entangled qubit (of type `FutureQubit`)
            * `pair` is a register holding which pair is handled (0, 1, ...)
        :param sequential: whether to use callbacks after each pair, defaults to False
        :param time_unit: which time unit to use for the `max_time` parameter
        :param max_time: maximum number of time units (see `time_unit`) the Host is
            willing to wait for entanglement generation of a single pair. If generation
            does not succeed within this time, the whole subroutine that this request
            is part of is reset and run again by the quantum node controller.
        :param min_fidelity_all_at_end: the minimum fidelity that *all* entangled
            qubits should ideally still have at the moment the last qubit has been
            generated. For example, when specifying `number=2` and
            `min_fidelity_all_at_end=80`, the the program will automatically try to
            make sure that both qubits have a fidelity of at least 80% when the
            second qubit has been generated. It will attempt to do this by
            automatically re-trying the entanglement generation if the fidelity
            constraint is not satisfied. This is however an *attempt*, and not
            a guarantee!.
        :param max_tries: maximum number of re-tries should be made to try and achieve
            the `min_fidelity_all_at_end` constraint.
        :return: list of qubits created
        """

        qubits, _ = self.conn.builder.sdk_create_epr_keep(
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=post_routine,
                sequential=sequential,
                time_unit=time_unit,
                max_time=max_time,
                min_fidelity_all_at_end=min_fidelity_all_at_end,
                max_tries=max_tries,
            ),
        )
        return qubits

    def create_keep_with_info(
        self,
        number: int = 1,
        post_routine: Optional[Callable] = None,
        sequential: bool = False,
        time_unit: TimeUnit = TimeUnit.MICRO_SECONDS,
        max_time: int = 0,
        min_fidelity_all_at_end: Optional[int] = None,
    ) -> Tuple[List[Qubit], List[EprKeepResult]]:
        """Same as create_keep but also return the EPR generation information coming
        from the network stack.

        For more information see the documentation of `create_keep`.

        :param number: number of pairs to generate, defaults to 1
        :return: tuple with (1) list of qubits created, (2) list of EprKeepResult objects
        """
        qubits, info = self.conn._builder.sdk_create_epr_keep(
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=post_routine,
                sequential=sequential,
                time_unit=time_unit,
                max_time=max_time,
                min_fidelity_all_at_end=min_fidelity_all_at_end,
            ),
        )
        return qubits, info

    def _get_rotations_from_basis(self, basis: EPRMeasBasis) -> Tuple[int, int, int]:
        if basis == EPRMeasBasis.X:
            return (0, 24, 0)
        elif basis == EPRMeasBasis.Y:
            return (8, 0, 0)
        elif basis == EPRMeasBasis.Z:
            return (0, 0, 0)
        elif basis == EPRMeasBasis.MX:
            return (0, 8, 0)
        elif basis == EPRMeasBasis.MY:
            return (24, 0, 0)
        elif basis == EPRMeasBasis.MZ:
            return (16, 0, 0)
        else:
            assert False, f"invalid EPRMeasBasis {basis}"

    def create_measure(
        self,
        number: int = 1,
        time_unit: TimeUnit = TimeUnit.MICRO_SECONDS,
        max_time: int = 0,
        basis_local: EPRMeasBasis = None,
        basis_remote: EPRMeasBasis = None,
        rotations_local: Tuple[int, int, int] = (0, 0, 0),
        rotations_remote: Tuple[int, int, int] = (0, 0, 0),
        random_basis_local: Optional[RandomBasis] = None,
        random_basis_remote: Optional[RandomBasis] = None,
    ) -> List[EprMeasureResult]:
        """Ask the network stack to generate EPR pairs with the remote node and
        measure them immediately (on both nodes).

        A `create_measure` operation must always be matched by a `recv_measure`
        operation on the remote node.

        This operation returns a list of Linklayer response objects. These objects
        contain information about the entanglement generation and includes the
        measurement outcome and basis used. Note that all values are `Future` objects.
        This means that the current subroutine must be flushed before the values
        become defined.

        An example for generating 10 pairs with another node that are immediately
        measured:

        .. code-block::

            # list of Futures that become defined when subroutine is flushed
            outcomes = []
            with NetQASMConnection("alice", epr_sockets=[epr_socket]):
                ent_infos = epr_socket.create(number=10, tp=EPRType.M)
                for ent_info in ent_infos:
                    outcomes.append(ent_info.measurement_outcome)

        The basis to measure in can also be specified. There are 3 ways to specify a
        basis:

        * using one of the `EPRMeasBasis` variants
        * by specifying 3 rotation angles, interpreted as an X-rotation, a Y-rotation
          and another X-rotation. For example, setting `rotations_local` to (8, 0, 0)
          means that before measuring, an X-rotation of 8*pi/16 = pi/2 radians is
          applied to the qubit.
        * using one of the `RandomBasis` variants, in which case one of the bases of
          that variant is chosen at random just before measuring

        NOTE: the node that initiates the entanglement generation, i.e. the one that
        calls `create` on its EPR socket, also controls the measurement bases of the
        receiving node (by setting e.g. `rotations_remote`). The receiving node cannot
        change this.

        :param number: number of EPR pairs to generate, defaults to 1
        :param time_unit: which time unit to use for the `max_time` parameter
        :param max_time: maximum number of time units (see `time_unit`) the Host is
            willing to wait for entanglement generation of a single pair. If generation
            does not succeed within this time, the whole subroutine that this request
            is part of is reset and run again by the quantum node controller.
        :param basis_local: basis to measure in on this node for M-type requests
        :param basis_remote: basis to measure in on the remote node for M-type requests
        :param rotations_local: rotations to apply before measuring on this node
        :param rotations_remote: rotations to apply before measuring on remote node
        :param random_basis_local: random bases to choose from when measuring on this
            node
        :param random_basis_remote: random bases to choose from when measuring on
            the remote node
        :return: list of entanglement info objects per created pair.
        """

        if basis_local is not None:
            rotations_local = self._get_rotations_from_basis(basis_local)
        if basis_remote is not None:
            rotations_remote = self._get_rotations_from_basis(basis_remote)

        return self.conn.builder.sdk_create_epr_measure(
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=None,
                sequential=False,
                time_unit=time_unit,
                max_time=max_time,
                random_basis_local=random_basis_local,
                random_basis_remote=random_basis_remote,
                rotations_local=rotations_local,
                rotations_remote=rotations_remote,
            ),
        )

    def create_rsp(
        self,
        number: int = 1,
        time_unit: TimeUnit = TimeUnit.MICRO_SECONDS,
        max_time: int = 0,
        basis_local: EPRMeasBasis = None,
        rotations_local: Tuple[int, int, int] = (0, 0, 0),
        random_basis_local: Optional[RandomBasis] = None,
        min_fidelity_all_at_end: Optional[int] = None,
    ) -> List[EprMeasureResult]:
        """Ask the network stack to do remote preparation with the remote node.

        A `create_rsp` operation must always be matched by a `recv_erp` operation
        on the remote node.

        This operation returns a list of Linklayer response objects. These objects
        contain information about the entanglement generation and includes the
        measurement outcome and basis used. Note that all values are `Future` objects.
        This means that the current subroutine must be flushed before the values
        become defined.

        An example for generating 10 pairs with another node that are immediately
        measured:

        .. code-block::

            m: LinkLayerOKTypeM = epr_socket.create_rsp(tp=EPRType.R)[0]
            print(m.measurement_outcome)
            # remote node now has a prepared qubit

        The basis to measure in can also be specified.
        There are 3 ways to specify a basis:

        * using one of the `EPRMeasBasis` variants
        * by specifying 3 rotation angles, interpreted as an X-rotation, a Y-rotation
          and another X-rotation. For example, setting `rotations_local` to (8, 0, 0)
          means that before measuring, an X-rotation of 8*pi/16 = pi/2 radians is
          applied to the qubit.
        * using one of the `RandomBasis` variants, in which case one of the bases of
          that variant is chosen at random just before measuring

        :param number: number of EPR pairs to generate, defaults to 1
        :param time_unit: which time unit to use for the `max_time` parameter
        :param max_time: maximum number of time units (see `time_unit`) the Host is
            willing to wait for entanglement generation of a single pair. If generation
            does not succeed within this time, the whole subroutine that this request
            is part of is reset and run again by the quantum node controller.
        :param basis_local: basis to measure in on this node for M-type requests
        :param basis_remote: basis to measure in on the remote node for M-type requests
        :param rotations_local: rotations to apply before measuring on this node
        :param rotations_remote: rotations to apply before measuring on remote node
        :param random_basis_local: random bases to choose from when measuring on this
            node
        :param random_basis_remote: random bases to choose from when measuring on
            the remote node
        :return: list of entanglement info objects per created pair.
        """

        if basis_local is not None:
            rotations_local = self._get_rotations_from_basis(basis_local)

        return self.conn.builder.sdk_create_epr_rsp(
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=None,
                sequential=False,
                time_unit=time_unit,
                max_time=max_time,
                random_basis_local=random_basis_local,
                rotations_local=rotations_local,
                min_fidelity_all_at_end=min_fidelity_all_at_end,
            )
        )

    def create(
        self,
        number: int = 1,
        post_routine: Optional[Callable] = None,
        sequential: bool = False,
        tp: EPRType = EPRType.K,
        time_unit: TimeUnit = TimeUnit.MICRO_SECONDS,
        max_time: int = 0,
        basis_local: EPRMeasBasis = None,
        basis_remote: EPRMeasBasis = None,
        rotations_local: Tuple[int, int, int] = (0, 0, 0),
        rotations_remote: Tuple[int, int, int] = (0, 0, 0),
        random_basis_local: Optional[RandomBasis] = None,
        random_basis_remote: Optional[RandomBasis] = None,
    ) -> Union[List[Qubit], List[EprMeasureResult], List[LinkLayerOKTypeM]]:
        """Ask the network stack to generate EPR pairs with the remote node.

        A `create` operation must always be matched by a `recv` operation on the remote
        node.

        If the type of request is Create and Keep (CK, or just K) and if `sequential`
        is False (default), this operation returns a list of Qubit objects representing
        the local qubits that are each one half of the generated pairs. These qubits
        can then be manipulated locally just like locally initialized qubits, by e.g.
        applying gates or measuring them.
        Each qubit also contains information about the entanglement generation that
        lead to its creation, and can be accessed by its `entanglement_info` property.

        A typical example for just generating one pair with another node would be:

        .. code-block::

            q = epr_socket.create()[0]
            # `q` can now be used as a normal qubit

        If the type of request is Measure Directly (MD, or just M), this operation
        returns a list of Linklayer response objects. These objects contain information
        about the entanglement generation and includes the measurement outcome and
        basis used. Note that all values are `Future` objects. This means that the
        current subroutine must be flushed before the values become defined.

        An example for generating 10 pairs with another node that are immediately
        measured:

        .. code-block::

            # list of Futures that become defined when subroutine is flushed
            outcomes = []
            with NetQASMConnection("alice", epr_sockets=[epr_socket]):
                ent_infos = epr_socket.create(number=10, tp=EPRType.M)
                for ent_info in ent_infos:
                    outcomes.append(ent_info.measurement_outcome)

        For "Measure Directly"-type requests, the basis to measure in can also be
        specified. There are 3 ways to specify a basis:

        * using one of the `EPRMeasBasis` variants
        * by specifying 3 rotation angles, interpreted as an X-rotation, a Y-rotation
          and another X-rotation. For example, setting `rotations_local` to (8, 0, 0)
          means that before measuring, an X-rotation of 8*pi/16 = pi/2 radians is
          applied to the qubit.
        * using one of the `RandomBasis` variants, in which case one of the bases of
          that variant is chosen at random just before measuring

        NOTE: the node that initiates the entanglement generation, i.e. the one that
        calls `create` on its EPR socket, also controls the measurement bases of the
        receiving node (by setting e.g. `rotations_remote`). The receiving node cannot
        change this.

        If `sequential` is False (default), the all requested EPR pairs are generated
        at once, before returning the results (qubits or entanglement info objects).

        If `sequential` is True, a callback function (`post_routine`) should be
        specified. After generating one EPR pair, this callback will be called, before
        generating the next pair. This method can e.g. be used to generate many EPR
        pairs (more than the number of physical qubits available), by measuring (and
        freeing up) each qubit before the next pair is generated.

        For example:

        .. code-block::

            outcomes = alice.new_array(num)

            def post_create(conn, q, pair):
                q.H()
                outcome = outcomes.get_future_index(pair)
                q.measure(outcome)
            epr_socket.create(number=num, post_routine=post_create, sequential=True)


        :param number: number of EPR pairs to generate, defaults to 1
        :param post_routine: callback function for each genated pair. Only used if
            `sequential` is True.
            The callback should take three arguments `(conn, q, pair)` where
            * `conn` is the connection (e.g. `self`)
            * `q` is the entangled qubit (of type `FutureQubit`)
            * `pair` is a register holding which pair is handled (0, 1, ...)
        :param sequential: whether to use callbacks after each pair, defaults to False
        :param tp: type of entanglement generation, defaults to EPRType.K. Note that
            corresponding `recv` of the remote node's EPR socket must specify the
            same type.
        :param time_unit: which time unit to use for the `max_time` parameter
        :param max_time: maximum number of time units (see `time_unit`) the Host is
            willing to wait for entanglement generation of a single pair. If generation
            does not succeed within this time, the whole subroutine that this request
            is part of is reset and run again by the quantum node controller.
        :param basis_local: basis to measure in on this node for M-type requests
        :param basis_remote: basis to measure in on the remote node for M-type requests
        :param rotations_local: rotations to apply before measuring on this node
            (for M-type requests)
        :param rotations_remote: rotations to apply before measuring on remote node
            (for M-type requests)
        :param random_basis_local: random bases to choose from when measuring on this
            node (for M-type requests)
        :param random_basis_remote: random bases to choose from when measuring on
            the remote node (for M-type requests)
        :return: For K-type requests: list of qubits created. For M-type requests:
            list of entanglement info objects per created pair.
        """

        self._logger.warning(
            "EPRSocket.create() is deprecated. Use one of "
            "create_keep, create_measure, or create_rsp instead."
        )

        if tp == EPRType.K:
            return self.create_keep(
                number=number,
                post_routine=post_routine,
                sequential=sequential,
                time_unit=time_unit,
                max_time=max_time,
            )
        elif tp == EPRType.M:
            return self.create_measure(
                number=number,
                time_unit=time_unit,
                max_time=max_time,
                basis_local=basis_local,
                basis_remote=basis_remote,
                rotations_local=rotations_local,
                rotations_remote=rotations_remote,
                random_basis_local=random_basis_local,
                random_basis_remote=random_basis_remote,
            )
        elif tp == EPRType.R:
            return self.create_rsp(
                number=number,
                time_unit=time_unit,
                max_time=max_time,
                basis_local=basis_local,
                random_basis_local=random_basis_local,
            )
        assert False

    def create_context(
        self,
        number: int = 1,
        sequential: bool = False,
        time_unit: TimeUnit = TimeUnit.MICRO_SECONDS,
        max_time: int = 0,
    ) -> ContextManager[Tuple[FutureQubit, RegFuture]]:
        """Create a context that is executed for each generated EPR pair consecutively.

        Creates EPR pairs with a remote node and handles each pair by
        the operations defined in a subsequent context. See the example below.

        .. code-block::

            with epr_socket.create_context(number=10) as (q, pair):
                q.H()
                m = q.measure()

        NOTE: even though all pairs are handled consecutively, they are still
        generated concurrently by the network stack. By setting `sequential` to True,
        the network stack only generates the next pair after the context for the
        previous pair has been executed, similar to using a callback (`post_routine`)
        in the `create` method.

        :param number: number of EPR pairs to generate, defaults to 1
        :param sequential: whether to generate pairs sequentially, defaults to False
        """
        return self.conn.builder.sdk_create_epr_context(
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=None,
                sequential=sequential,
                time_unit=time_unit,
                max_time=max_time,
            )
        )

    def recv_keep(
        self,
        number: int = 1,
        post_routine: Optional[Callable] = None,
        sequential: bool = False,
        min_fidelity_all_at_end: Optional[int] = None,
        max_tries: Optional[int] = None,
    ) -> List[Qubit]:
        """Ask the network stack to wait for the remote node to generate EPR pairs,
        which are kept in memory.

        A `recv_keep` operation must always be matched by a `create_keep` operation on
        the remote node. The number of generated pairs must also match.

        For more information see the documentation of `create_keep`.

        :param number: number of pairs to generate, defaults to 1
        :param post_routine: callback function used when `sequential` is True
        :param sequential: whether to call the callback after each pair generation,
            defaults to False
        :param min_fidelity_all_at_end: the minimum fidelity that *all* entangled
            qubits should ideally still have at the moment the last qubit has been
            generated. For example, when specifying `number=2` and
            `min_fidelity_all_at_end=80`, the the program will automatically try to
            make sure that both qubits have a fidelity of at least 80% when the
            second qubit has been generated. It will attempt to do this by
            automatically re-trying the entanglement generation if the fidelity
            constraint is not satisfied. This is however an *attempt*, and not
            a guarantee!.
        :param max_tries: maximum number of re-tries should be made to try and achieve
            the `min_fidelity_all_at_end` constraint.
        :return: list of qubits created
        """

        if self.conn is None:
            raise RuntimeError("EPRSocket does not have an open connection")

        qubits, _ = self.conn._builder.sdk_recv_epr_keep(
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=post_routine,
                sequential=sequential,
                min_fidelity_all_at_end=min_fidelity_all_at_end,
                max_tries=max_tries,
            ),
        )
        return qubits

    def recv_keep_with_info(
        self,
        number: int = 1,
        post_routine: Optional[Callable] = None,
        sequential: bool = False,
        min_fidelity_all_at_end: Optional[int] = None,
        max_tries: Optional[int] = None,
    ) -> Tuple[List[Qubit], List[EprKeepResult]]:
        """Same as recv_keep but also return the EPR generation information coming
        from the network stack.

        For more information see the documentation of `recv_keep`.

        :param number: number of pairs to generate, defaults to 1
        :return: tuple with (1) list of qubits created, (2) list of EprKeepResult objects
        """
        qubits, info = self.conn._builder.sdk_recv_epr_keep(
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=post_routine,
                sequential=sequential,
                min_fidelity_all_at_end=min_fidelity_all_at_end,
                max_tries=max_tries,
            ),
        )
        return qubits, info

    def recv_measure(
        self,
        number: int = 1,
    ) -> List[EprMeasureResult]:
        """Ask the network stack to wait for the remote node to generate EPR pairs,
        which are immediately measured (on both nodes).

        A `recv_measure` operation must always be matched by a `create_measure`
        operation on the remote node. The number and type of generation must also match.

        For more information see the documentation of `create_measure`.

        :param number: number of pairs to generate, defaults to 1
        :param post_routine: callback function used when `sequential` is True
        :param sequential: whether to call the callback after each pair generation,
            defaults to False
        :return: list of entanglement info objects per created pair.
        """
        if self.conn is None:
            raise RuntimeError("EPRSocket does not have an open connection")

        return self.conn.builder.sdk_recv_epr_measure(
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=None,
                sequential=False,
            ),
        )

    def recv_rsp(
        self,
        number: int = 1,
        min_fidelity_all_at_end: Optional[int] = None,
        max_tries: Optional[int] = None,
    ) -> List[Qubit]:
        """Ask the network stack to wait for remote state preparation from another node.

        A `recv_rsp` operation must always be matched by a `create_rsp` operation on
        the remote node. The number and type of generation must also match.

        For more information see the documentation of `create_rsp`.

        :param number: number of pairs to generate, defaults to 1
        :return: list of qubits created
        """
        if self.conn is None:
            raise RuntimeError("EPRSocket does not have an open connection")

        qubits, _ = self.conn.builder.sdk_recv_epr_rsp(
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=None,
                sequential=False,
                min_fidelity_all_at_end=min_fidelity_all_at_end,
                max_tries=max_tries,
            ),
        )
        return qubits

    def recv_rsp_with_info(
        self,
        number: int = 1,
        min_fidelity_all_at_end: Optional[int] = None,
        max_tries: Optional[int] = None,
    ) -> Tuple[List[Qubit], List[EprKeepResult]]:
        """Same as recv_rsp but also return the EPR generation information coming
        from the network stack.

        For more information see the documentation of `recv_rsp`.

        :param number: number of pairs to generate, defaults to 1
        :return: tuple with (1) list of qubits created, (2) list of EprKeepResult objects
        """
        if self.conn is None:
            raise RuntimeError("EPRSocket does not have an open connection")

        qubits, infos = self.conn.builder.sdk_recv_epr_rsp(
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=None,
                sequential=False,
                min_fidelity_all_at_end=min_fidelity_all_at_end,
                max_tries=max_tries,
            ),
        )
        return qubits, infos

    def recv(
        self,
        number: int = 1,
        post_routine: Optional[Callable] = None,
        sequential: bool = False,
        tp: EPRType = EPRType.K,
    ) -> Union[List[Qubit], List[EprMeasureResult], List[LinkLayerOKTypeR]]:
        """Ask the network stack to wait for the remote node to generate EPR pairs.

        A `recv` operation must always be matched by a `create` operation on the remote
        node. See also the documentation of `create`.
        The number and type of generation must also match.

        In case of Measure Directly requests, it is the initiating node (that calls
        `create`) which specifies the measurement bases. This should not and cannot be
        done in `recv`.

        For more information see the documentation of `create`.

        :param number: number of pairs to generate, defaults to 1
        :param post_routine: callback function used when `sequential` is True
        :param sequential: whether to call the callback after each pair generation,
            defaults to False
        :param tp: type of entanglement generation, defaults to EPRType.K
        :return: For K-type requests: list of qubits created. For M-type requests:
            list of entanglement info objects per created pair.
        """
        self._logger.warning(
            "EPRSocket.recv() is deprecated. Use one of "
            "recv_keep, recv_measure, or recv_rsp instead."
        )

        if tp == EPRType.K:
            return self.recv_keep(
                number=number,
                post_routine=post_routine,
                sequential=sequential,
            )
        elif tp == EPRType.M:
            return self.recv_measure(number=number)
        elif tp == EPRType.R:
            return self.recv_rsp(number=number)
        assert False

    @contextmanager
    def recv_context(
        self,
        number: int = 1,
        sequential: bool = False,
    ):
        """Receives EPR pair with a remote node (see doc of :meth:`~.create_context`)"""
        try:
            # NOTE loop_register is the register used for looping over the generated pairs
            (
                pre_commands,
                loop_register,
                ent_results_array,
                output,
                pair,
            ) = self.conn.builder._pre_epr_context(
                role=EPRRole.RECV,
                params=EntRequestParams(
                    remote_node_id=self.remote_node_id,
                    epr_socket_id=self._epr_socket_id,
                    number=number,
                    post_routine=None,
                    sequential=sequential,
                ),
            )
            yield output, pair
        finally:
            self.conn.builder._post_epr_context(
                pre_commands=pre_commands,
                number=number,
                loop_register=loop_register,
                ent_results_array=ent_results_array,
                pair=pair,
            )

    def _get_node_id(self, app_name: str) -> int:
        return self.conn.network_info.get_node_id_for_app(app_name=app_name)
