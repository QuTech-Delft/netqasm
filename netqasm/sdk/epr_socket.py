"""EPR Socket interface."""

from __future__ import annotations

import abc
import logging
from contextlib import contextmanager
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple, Union

from netqasm.lang.ir import GenericInstr
from netqasm.logging.glob import get_netqasm_logger
from netqasm.qlink_compat import (
    EPRType,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerOKTypeR,
    RandomBasis,
    TimeUnit,
)
from netqasm.sdk.builder import EntRequestParams

from .qubit import Qubit

if TYPE_CHECKING:
    from netqasm.sdk.connection import BaseNetQASMConnection

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
        self._conn: Optional[BaseNetQASMConnection] = None
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
    def conn(self) -> BaseNetQASMConnection:
        """Get the underlying :class:`NetQASMConnection`"""
        if self._conn is None:
            raise RuntimeError("EPRSocket does not have an open connection")
        return self._conn

    @conn.setter
    def conn(self, conn: BaseNetQASMConnection):
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
    ) -> Union[
        List[Qubit],
        List[LinkLayerOKTypeK],
        List[LinkLayerOKTypeM],
        List[LinkLayerOKTypeR],
    ]:
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

        # TODO: don't hard-code the assumption that rotation values are in multiples
        #       of pi/16
        if basis_local == EPRMeasBasis.X:
            rotations_local = (0, 24, 0)
        elif basis_local == EPRMeasBasis.Y:
            rotations_local = (8, 0, 0)
        elif basis_local == EPRMeasBasis.Z:
            rotations_local = (0, 0, 0)
        elif basis_local == EPRMeasBasis.MX:
            rotations_local = (0, 8, 0)
        elif basis_local == EPRMeasBasis.MY:
            rotations_local = (24, 0, 0)
        elif basis_local == EPRMeasBasis.MZ:
            rotations_local = (16, 0, 0)
        elif basis_local is None:
            pass  # use rotations_local argument value
        else:
            raise ValueError(f"Unsupported EPR measurement basis: {basis_local}")

        if basis_remote == EPRMeasBasis.X:
            rotations_remote = (0, 24, 0)
        elif basis_remote == EPRMeasBasis.Y:
            rotations_remote = (8, 0, 0)
        elif basis_remote == EPRMeasBasis.Z:
            rotations_remote = (0, 0, 0)
        elif basis_remote == EPRMeasBasis.MX:
            rotations_remote = (0, 8, 0)
        elif basis_remote == EPRMeasBasis.MY:
            rotations_remote = (24, 0, 0)
        elif basis_remote == EPRMeasBasis.MZ:
            rotations_remote = (16, 0, 0)
        elif basis_remote is None:
            pass  # use rotations_remote argument value
        else:
            raise ValueError(f"Unsupported EPR measurement basis: {basis_remote}")

        return self.conn._builder.create_epr(  # type: ignore
            tp=tp,
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=post_routine,
                sequential=sequential,
                time_unit=time_unit,
                max_time=max_time,
                random_basis_local=random_basis_local,
                random_basis_remote=random_basis_remote,
                rotations_local=rotations_local,
                rotations_remote=rotations_remote,
            ),
        )

    @contextmanager
    def create_context(
        self,
        number: int = 1,
        sequential: bool = False,
        time_unit: TimeUnit = TimeUnit.MICRO_SECONDS,
        max_time: int = 0,
    ):
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
        try:
            instruction = GenericInstr.CREATE_EPR
            # NOTE loop_register is the register used for looping over the generated pairs
            (
                pre_commands,
                loop_register,
                ent_results_array,
                output,
                pair,
            ) = self.conn._builder._pre_epr_context(
                instruction=instruction,
                tp=EPRType.K,
                params=EntRequestParams(
                    remote_node_id=self.remote_node_id,
                    epr_socket_id=self._epr_socket_id,
                    number=number,
                    post_routine=None,
                    sequential=sequential,
                    time_unit=time_unit,
                    max_time=max_time,
                ),
            )
            yield output, pair
        finally:
            self.conn._builder._post_epr_context(
                pre_commands=pre_commands,
                number=number,
                loop_register=loop_register,
                ent_results_array=ent_results_array,
                pair=pair,
            )

    def recv(
        self,
        number: int = 1,
        post_routine: Optional[Callable] = None,
        sequential: bool = False,
        tp: EPRType = EPRType.K,
    ) -> Union[List[Qubit], T_LinkLayerOkList]:
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

        if self.conn is None:
            raise RuntimeError("EPRSocket does not have an open connection")

        return self.conn._builder.recv_epr(
            tp=tp,
            params=EntRequestParams(
                remote_node_id=self.remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                post_routine=post_routine,
                sequential=sequential,
            ),
        )

    @contextmanager
    def recv_context(
        self,
        number: int = 1,
        sequential: bool = False,
    ):
        """Receives EPR pair with a remote node (see doc of :meth:`~.create_context`)"""
        try:
            instruction = GenericInstr.RECV_EPR
            # NOTE loop_register is the register used for looping over the generated pairs
            (
                pre_commands,
                loop_register,
                ent_results_array,
                output,
                pair,
            ) = self.conn._builder._pre_epr_context(
                instruction=instruction,
                tp=EPRType.K,
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
            self.conn._builder._post_epr_context(
                pre_commands=pre_commands,
                number=number,
                loop_register=loop_register,
                ent_results_array=ent_results_array,
                pair=pair,
            )

    def _get_node_id(self, app_name: str) -> int:
        return self.conn.network_info.get_node_id_for_app(app_name=app_name)
