import abc
from contextlib import contextmanager

from qlink_interface import EPRType

from netqasm.logging import get_netqasm_logger
from netqasm.instructions.instr_enum import Instruction


class NoCircuitError(RuntimeError):
    pass


def _assert_has_conn(method):
    def new_method(self, *args, **kwargs):
        if self._conn is None:
            raise NoCircuitError("To use the socket it first needs to be setup by giving it to a `NetQASMConnection`")
        return method(self, *args, **kwargs)
    return new_method


class EPRSocket(abc.ABC):
    def __init__(
        self,
        remote_node_name,
        epr_socket_id=0,
        remote_epr_socket_id=0,
    ):
        """Encapsulates the notion of an EPR socket which sets up a virtual circuit in the network
        when instantiated and can then be used for entanglement generation.

        Parameters
        ----------
        remote_node_name : str
            Name of the remote node to entangle with.
        epr_socket_id : int
            The identifier used for this socket.
        remote_epr_socket_id : int
            The identifier used by the remote node.
        """
        self._conn = None
        self._remote_node_name = remote_node_name
        self._remote_node_id = None  # Gets set when the connection is set
        self._epr_socket_id = epr_socket_id
        self._remote_epr_socket_id = remote_epr_socket_id

        self._logger = get_netqasm_logger(f"{self.__class__.__name__}({self._remote_node_name}, {self._epr_socket_id})")

    @property
    def conn(self):
        return self._conn

    @conn.setter
    def conn(self, conn):
        self._conn = conn
        self._remote_node_id = self._get_node_id(node_name=self._remote_node_name)

    @_assert_has_conn
    def create(
        self,
        number=1,
        post_routine=None,
        sequential=False,
        tp=EPRType.K,
        random_basis_local=None,
        random_basis_remote=None,
    ):
        """Creates EPR pair with a remote node

        Parameters
        ----------
        number : int
            The number of pairs to create
        post_routine : function
            Can be used to specify what should happen when entanglement is generated
            for each pair.
            The function should take three arguments `(conn, q, pair)` where
            * `conn` is the connection (e.g. `self`)
            * `q` is the entangled qubit (of type :class:`netqasm.qubit._FutureQubit`)
            * `pair` is a loop register stating which pair is handled (0, 1, ...)

            for example to state that the qubit should be measured in the Hadamard basis
            one can provide the following function

            >>> def post_create(conn, q, pair):
            >>>     q.H()
            >>>     q.measure(future=outcomes.get_future_index(pair))

            where `outcomes` is an already allocated array and `pair` is then used to
            put the outcome at the correct index of the array.

            NOTE: If the a qubit is measured (not inplace) in a `post_routine` but is
            also used by acting on the returned objects of `createEPR` this cannot
            be checked in compile-time and will raise an error during the execution
            of the full subroutine in the backend.
        sequential : bool, optional
            If this is specified to `True` each qubit will have the same virtual address
            and there will maximally be one pair in memory at a given time.
            If `number` is greater than 1 a post_routine should be specified which
            consumed each pair.

            NOTE: If `sequential` is `False` (default), `number` cannot be greater than
                  the size of the unit module. However, if `sequential` is `True` is can.
        tp : :class:`~.EPRType`
            What type of request, i.e. either `K` (create and keep),
            `M` (measure-directly) or `R` (remote state preparation).
            Depending on the type of request the method will return different things,
            for example if the request is of type `K` a list of qubits will be returned:

            >>> qubits = epr_socket.create(number=3, tp=EPRType.K)
            >>> for q in qubits:
            >>>     q.H()

            however for type `M` requests it will be a list of entanglement generations:

            >>> ent_infos = epr_socket.create(number=3, tp=EPRType.K)
            >>> for ent_info in ent_infos:
            >>>     assert isinstance(ent_info, tuple)
        """
        return self._conn._create_epr(
            remote_node_id=self._remote_node_id,
            epr_socket_id=self._epr_socket_id,
            number=number,
            post_routine=post_routine,
            sequential=sequential,
            tp=tp,
            random_basis_local=random_basis_local,
            random_basis_remote=random_basis_remote,
        )

    @contextmanager
    @_assert_has_conn
    def create_context(self, number=1, sequential=False):
        """Creates EPR pairs with a remote node and handles each pair by
        the operations defined in a subsequent context, see example below.

        Example
        -------
        To create two pairs and measure both of these in the Hadamard basis one can do as follows:
        >>> with epr_socket.create_context(number=num) as (q, pair):
        >>>     q.H()
        >>>     m = q.measure()

        NOTE: The `sequential` flag can be used to specify if the qubits should use the same
        virtual qubit and there only exists one at a time or not.


        Parameters
        ----------
        number : int
            The number of pairs to create
        post_routine : function
            Can be used to specify what should happen when entanglement is generated
            for each pair.
            The function should take three arguments `(conn, q, pair)` where
            * `conn` is the connection (e.g. `self`)
            * `q` is the entangled qubit (of type :class:`netqasm.qubit._FutureQubit`)
            * `pair` is a loop register stating which pair is handled (0, 1, ...)

            for example to state that the qubit should be measured in the Hadamard basis
            one can provide the following function

            >>> def post_create(conn, q, pair):
            >>>     q.H()
            >>>     q.measure(future=outcomes.get_future_index(pair))

            where `outcomes` is an already allocated array and `pair` is then used to
            put the outcome at the correct index of the array.

            NOTE: If the a qubit is measured (not inplace) in a `post_routine` but is
            also used by acting on the returned objects of `createEPR` this cannot
            be checked in compile-time and will raise an error during the execution
            of the full subroutine in the backend.
        sequential : bool, optional
            If this is specified to `True` each qubit will have the same virtual address
            and there will maximally be one pair in memory at a given time.
            If `number` is greater than 1 a post_routine should be specified which
            consumed each pair.

            NOTE: If `sequential` is `False` (default), `number` cannot be greater than
                  the size of the unit module. However, if `sequential` is `True` is can.
        """
        try:
            instruction = Instruction.CREATE_EPR
            # NOTE loop_register is the register used for looping over the generated pairs
            pre_commands, loop_register, ent_info_array, output, pair = self._conn._pre_epr_context(
                instruction=instruction,
                remote_node_id=self._remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                sequential=sequential,
                tp=EPRType.K,
            )
            yield output, pair
        finally:
            self._conn._post_epr_context(
                pre_commands=pre_commands,
                number=number,
                loop_register=loop_register,
                ent_info_array=ent_info_array,
                pair=pair,
            )

    @_assert_has_conn
    def recv(self, number=1, post_routine=None, sequential=False, tp=EPRType.K):
        """Receives EPR pair with a remote node (see doc of :meth:`~.create`)"""
        return self._conn._recv_epr(
            remote_node_id=self._remote_node_id,
            epr_socket_id=self._epr_socket_id,
            number=number,
            post_routine=post_routine,
            sequential=sequential,
            tp=tp,
        )

    @contextmanager
    @_assert_has_conn
    def recv_context(self, number=1, sequential=False):
        """Receives EPR pair with a remote node (see doc of :meth:`~.create_context`)"""
        try:
            instruction = Instruction.RECV_EPR
            # NOTE loop_register is the register used for looping over the generated pairs
            pre_commands, loop_register, ent_info_array, output, pair = self._conn._pre_epr_context(
                instruction=instruction,
                remote_node_id=self._remote_node_id,
                epr_socket_id=self._epr_socket_id,
                number=number,
                sequential=sequential,
                tp=EPRType.K,
            )
            yield output, pair
        finally:
            self._conn._post_epr_context(
                pre_commands=pre_commands,
                number=number,
                loop_register=loop_register,
                ent_info_array=ent_info_array,
                pair=pair,
            )

    @_assert_has_conn
    def _get_node_id(self, node_name):
        return self._conn._get_node_id(node_name=node_name)