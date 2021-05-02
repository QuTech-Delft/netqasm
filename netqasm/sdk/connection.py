"""TODO write about connections"""

from __future__ import annotations

import abc
import logging
import math
import os
import pickle
from itertools import count
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from netqasm import NETQASM_VERSION
from netqasm.backend.messages import (
    InitNewAppMessage,
    Message,
    OpenEPRSocketMessage,
    Signal,
    SignalMessage,
    StopAppMessage,
    SubroutineMessage,
)
from netqasm.lang import operand
from netqasm.lang.ir import BranchLabel, ICmd, PreSubroutine
from netqasm.lang.subroutine import Subroutine
from netqasm.logging.glob import get_netqasm_logger
from netqasm.qlink_compat import (
    EPRType,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerOKTypeR,
)
from netqasm.sdk.compiling import SubroutineCompiler
from netqasm.sdk.config import LogConfig
from netqasm.sdk.futures import Array, Future, RegFuture
from netqasm.sdk.network import NetworkInfo
from netqasm.sdk.progress_bar import ProgressBar
from netqasm.sdk.qubit import Qubit, _FutureQubit
from netqasm.sdk.shared_memory import SharedMemory, SharedMemoryManager
from netqasm.util.log import LineTracker

from .builder import Builder

T_Cmd = Union[ICmd, BranchLabel]
T_LinkLayerOkList = Union[
    List[LinkLayerOKTypeK], List[LinkLayerOKTypeM], List[LinkLayerOKTypeR]
]
T_Message = Union[Message, SubroutineMessage]
T_CValue = Union[int, Future, RegFuture]
T_PostRoutine = Callable[
    ["BaseNetQASMConnection", Union[_FutureQubit, List[Future]], operand.Register], None
]
T_BranchRoutine = Callable[["BaseNetQASMConnection"], None]
T_LoopRoutine = Callable[["BaseNetQASMConnection"], None]

if TYPE_CHECKING:
    from netqasm.sdk.epr_socket import EPRSocket


# NOTE this is needed to be able to instanciate tuples the same way as namedtuples
class _Tuple(tuple):
    @classmethod
    def __new__(cls, *args, **kwargs):
        return tuple.__new__(cls, args[1:])


class BaseNetQASMConnection(abc.ABC):

    # Global dict to track all used app IDs for each program
    _app_ids: Dict[str, List[int]] = {}  # <party> -> [<app_id1>, <app_id2>, ...]

    # Dict[node_name, Dict[app_id, app_name]]
    _app_names: Dict[str, Dict[int, str]] = {}

    # Class to use to pack entanglement information
    ENT_INFO = {
        EPRType.K: LinkLayerOKTypeK,
        EPRType.M: LinkLayerOKTypeM,
        EPRType.R: LinkLayerOKTypeR,
    }

    def __init__(
        self,
        app_name: str,
        node_name: Optional[str] = None,
        app_id: Optional[int] = None,
        max_qubits: int = 5,
        log_config: LogConfig = None,
        epr_sockets: Optional[List[EPRSocket]] = None,
        compiler: Optional[Type[SubroutineCompiler]] = None,
        return_arrays: bool = True,
        _init_app: bool = True,
        _setup_epr_sockets: bool = True,
    ):
        self._app_name: str = app_name

        # Set an app ID
        self._app_id: int = self._get_new_app_id(app_id)

        if node_name is None:
            node_name = self.network_info.get_node_name_for_app(app_name)
        self._node_name: str = node_name

        if node_name not in self._app_names:
            self._app_names[node_name] = {}
        self._app_names[node_name][self._app_id] = app_name

        # All qubits active for this connection
        self.active_qubits: List[Qubit] = []

        self._shared_memory: Optional[
            SharedMemory
        ] = SharedMemoryManager.get_shared_memory(self.node_name, key=self._app_id)

        # Can be set to false for e.g. debugging, not exposed to user atm
        self._clear_app_on_exit: bool = True
        self._stop_backend_on_exit: bool = True

        if log_config is None:
            log_config = LogConfig()

        self._line_tracker: LineTracker = LineTracker(log_config=log_config)
        self._track_lines: bool = log_config.track_lines

        # Should subroutines commited be saved for logging/debugging
        self._log_subroutines_dir: Optional[str] = log_config.log_subroutines_dir
        # Commited subroutines saved for logging/debugging
        self._commited_subroutines: List[Subroutine] = []

        self._builder = Builder(
            connection=self,
            max_qubits=max_qubits,
            epr_sockets=epr_sockets,
            compiler=compiler,
            return_arrays=return_arrays,
        )

        # What compiler (if any) to be used
        self._compiler: Optional[Type[SubroutineCompiler]] = compiler

        self._logger: logging.Logger = get_netqasm_logger(
            f"{self.__class__.__name__}({self.app_name})"
        )

        if _init_app:
            self._init_new_app(max_qubits=max_qubits)

        if _setup_epr_sockets:
            # Setup epr sockets
            self._setup_epr_sockets(epr_sockets=epr_sockets)

    @property
    def app_name(self) -> str:
        """Get the application name"""
        return self._app_name

    @property
    def node_name(self) -> str:
        """Get the node name"""
        return self._node_name

    @property
    def app_id(self) -> int:
        """Get the application ID"""
        return self._app_id

    @abc.abstractmethod
    def _get_network_info(self) -> Type[NetworkInfo]:
        raise NotImplementedError

    @property
    def network_info(self) -> Type[NetworkInfo]:
        return self._get_network_info()

    @classmethod
    def get_app_ids(cls) -> Dict[str, List[int]]:
        return cls._app_ids

    @classmethod
    def get_app_names(cls) -> Dict[str, Dict[int, str]]:
        return cls._app_names

    def __str__(self):
        return (
            f"NetQASM connection for app '{self.app_name}' with node '{self.node_name}'"
        )

    def __enter__(self):
        """Used to open the connection in a context.

        This is the intended behaviour of the connection.
        Operations specified using the connection or a qubit created with it gets combined into a
        subroutine, until either :meth:`~.flush` is called or the connection goes out of context
        which calls :meth:`~.__exit__`.

        .. code-block::

            # Open the connection
            with NetQASMConnection(app_name="alice") as alice:
                # Create a qubit
                q = Qubit(alice)
                # Perform a Hadamard
                q.H()
                # Measure the qubit
                m = q.measure()
                # Flush the subroutine to populate the variable `m` with the outcome
                # Alternetively, this can be done by letting the connection
                # go out of context and move the print to after.
                alice.flush()
                print(m)
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """TODO describe"""
        # Allow to not clear the app or stop the backend upon exit, for debugging and post processing
        self.close(
            clear_app=self._clear_app_on_exit,
            stop_backend=self._stop_backend_on_exit,
        )

    def _get_new_app_id(self, app_id: Optional[int]) -> int:
        """Finds a new app ID if not specific"""
        name = self.app_name
        if name not in self._app_ids:
            self._app_ids[name] = []

        # Which app_id
        if app_id is None:
            for app_id in count(0):
                if app_id not in self._app_ids[name]:
                    self._app_ids[name].append(app_id)
                    return app_id
            raise RuntimeError("This should never be reached")
        else:
            if app_id in self._app_ids[name]:
                raise ValueError("app_id={} is already in use".format(app_id))
            self._app_ids[name].append(app_id)
            return app_id

    def _pop_app_id(self) -> None:
        """
        Removes the used app ID from the list.
        """
        try:
            self._app_ids[self.app_name].remove(self.app_id)
        except ValueError:
            pass  # Already removed

    def clear(self) -> None:
        self._pop_app_id()

    def close(self, clear_app: bool = True, stop_backend: bool = False) -> None:
        """Handle exiting of context."""
        # Flush all pending commands
        self.flush()

        self._pop_app_id()

        self._signal_stop(clear_app=clear_app, stop_backend=stop_backend)
        self._inactivate_qubits()

        if self._log_subroutines_dir is not None:
            self._save_log_subroutines()

    def _commit_message(
        self, msg: T_Message, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        """Commit a message to the backend/qnodeos"""
        self._logger.debug(f"Committing message {msg}")
        self._commit_serialized_message(
            raw_msg=bytes(msg), block=block, callback=callback
        )

    @abc.abstractmethod
    def _commit_serialized_message(
        self, raw_msg: bytes, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        """Commit a message to the backend/qnodeos"""
        # Should be subclassed
        pass

    def _inactivate_qubits(self) -> None:
        while len(self.active_qubits) > 0:
            q = self.active_qubits.pop()
            q.active = False

    def _signal_stop(self, clear_app: bool = True, stop_backend: bool = True) -> None:
        if clear_app:
            self._commit_message(msg=StopAppMessage(app_id=self._app_id))

        if stop_backend:
            self._commit_message(msg=SignalMessage(signal=Signal.STOP), block=False)

    def _save_log_subroutines(self) -> None:
        filename = f"subroutines_{self.app_name}.pkl"
        filepath = os.path.join(self._log_subroutines_dir, filename)  # type: ignore
        with open(filepath, "wb") as f:
            pickle.dump(self._commited_subroutines, f)

    @property
    def shared_memory(self) -> SharedMemory:
        if self._shared_memory is None:
            mem = SharedMemoryManager.get_shared_memory(
                self.node_name, key=self._app_id
            )
            if mem is None:
                raise RuntimeError(
                    "Trying to access connection's shared memory, but it does not exist"
                )
            self._shared_memory = mem
        return self._shared_memory

    def _init_new_app(self, max_qubits: int) -> None:
        """Informs the backend of the new application and how many qubits it will maximally use"""
        self._commit_message(
            msg=InitNewAppMessage(
                app_id=self._app_id,
                max_qubits=max_qubits,
            )
        )
        while self.shared_memory is None:
            pass

    def _setup_epr_sockets(self, epr_sockets: Optional[List[EPRSocket]]) -> None:
        if epr_sockets is None:
            return
        for epr_socket in epr_sockets:
            if epr_socket._remote_app_name == self.app_name:
                raise ValueError("A node cannot setup an EPR socket with itself")
            epr_socket.conn = self
            self._setup_epr_socket(
                epr_socket_id=epr_socket.epr_socket_id,
                remote_node_id=epr_socket.remote_node_id,
                remote_epr_socket_id=epr_socket.remote_epr_socket_id,
                min_fidelity=epr_socket.min_fidelity,
            )

    def _setup_epr_socket(
        self,
        epr_socket_id: int,
        remote_node_id: int,
        remote_epr_socket_id: int,
        min_fidelity: int,
    ) -> None:
        """Sets up a new epr socket"""
        self._commit_message(
            msg=OpenEPRSocketMessage(
                app_id=self._app_id,
                epr_socket_id=epr_socket_id,
                remote_node_id=remote_node_id,
                remote_epr_socket_id=remote_epr_socket_id,
                min_fidelity=min_fidelity,
            )
        )

    def flush(self, block: bool = True, callback: Optional[Callable] = None) -> None:
        subroutine = self._builder._pop_pending_subroutine()
        if subroutine is None:
            return

        self._commit_subroutine(
            presubroutine=subroutine,
            block=block,
            callback=callback,
        )

    def _commit_subroutine(
        self,
        presubroutine: PreSubroutine,
        block: bool = True,
        callback: Optional[Callable] = None,
    ) -> None:
        self._logger.debug(f"Flushing presubroutine:\n{presubroutine}")

        # Parse, assembly and possibly compile the subroutine
        subroutine = self._builder._pre_process_subroutine(presubroutine)
        self._logger.info(f"Flushing compiled subroutine:\n{subroutine}")

        # Commit the subroutine to the quantum device
        self._commit_message(
            msg=SubroutineMessage(subroutine=subroutine),
            block=block,
            callback=callback,
        )

        self._builder._reset()

    def _subroutine_from_commands(self, commands: List[T_Cmd]) -> PreSubroutine:
        # Build sub-routine
        metadata = self._get_metadata()
        return PreSubroutine(**metadata, commands=commands)  # type: ignore

    def _get_metadata(self) -> Dict:
        return {
            "netqasm_version": NETQASM_VERSION,
            "app_id": self._app_id,
        }

    def _log_subroutine(self, subroutine: Subroutine) -> None:
        self._commited_subroutines.append(subroutine)

    def block(self) -> None:
        """Block until flushed subroutines finish"""
        raise NotImplementedError

    def new_array(
        self, length: int = 1, init_values: Optional[List[Optional[int]]] = None
    ) -> Array:
        return self._builder.new_array(length, init_values)

    def loop(
        self,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[operand.Register] = None,
    ) -> Iterator[operand.Register]:
        return self._builder.loop(stop, start, step, loop_register)  # type: ignore

    def loop_body(
        self,
        body: T_LoopRoutine,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[operand.Register] = None,
    ) -> None:
        self._builder.loop_body(body, stop, start, step, loop_register)

    def if_eq(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a == b"""
        self._builder.if_eq(a, b, body)

    def if_ne(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a != b"""
        self._builder.if_ne(a, b, body)

    def if_lt(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a < b"""
        self._builder.if_lt(a, b, body)

    def if_ge(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a >= b"""
        self._builder.if_ge(a, b, body)

    def if_ez(self, a: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a == 0"""
        self._builder.if_ez(a, body)

    def if_nz(self, a: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a != 0"""
        self._builder.if_nz(a, body)

    def tomography(
        self,
        preparation: Callable[[BaseNetQASMConnection], Qubit],
        iterations: int,
        progress: bool = True,
    ) -> Dict[str, float]:
        """
        Does a tomography on the output from the preparation specified.
        The frequencies from X, Y and Z measurements are returned as a tuple (f_X,f_Y,f_Z).

        - **Arguments**

            :preparation:     A function that takes a NetQASMConnection as input and prepares a qubit and returns this
            :iterations:     Number of measurements in each basis.
            :progress_bar:     Displays a progress bar
        """
        outcomes: Dict[str, List[Union[Future, RegFuture]]] = {
            "X": [],
            "Y": [],
            "Z": [],
        }
        if progress:
            bar = ProgressBar(3 * iterations)

        # Measure in X
        for _ in range(iterations):
            # Progress bar
            if progress:
                bar.increase()

            # prepare and measure
            q = preparation(self)
            q.H()
            m = q.measure()
            outcomes["X"].append(m)

        # Measure in Y
        for _ in range(iterations):
            # Progress bar
            if progress:
                bar.increase()

            # prepare and measure
            q = preparation(self)
            q.K()
            m = q.measure()
            outcomes["Y"].append(m)

        # Measure in Z
        for _ in range(iterations):
            # Progress bar
            if progress:
                bar.increase()

            # prepare and measure
            q = preparation(self)
            m = q.measure()
            outcomes["Z"].append(m)

        if progress:
            bar.close()
            del bar

        self.flush()

        freqs = {key: sum(value) / iterations for key, value in outcomes.items()}
        return freqs

    def test_preparation(
        self,
        preparation: Callable[[BaseNetQASMConnection], Qubit],
        exp_values: Tuple[float, float, float],
        conf: float = 2,
        iterations: int = 100,
        progress: bool = True,
    ) -> bool:
        """Test the preparation of a qubit.
        Returns True if the expected values are inside the confidence interval produced from the data received from
        the tomography function

        - **Arguments**

            :preparation:     A function that takes a NetQASMConnection as input and prepares a qubit and returns this
            :exp_values:     The expected values for measurements in the X, Y and Z basis.
            :conf:         Determines the confidence region (+/- conf/sqrt(iterations) )
            :iterations:     Number of measurements in each basis.
            :progress_bar:     Displays a progress bar
        """
        epsilon = conf / math.sqrt(iterations)

        freqs = self.tomography(preparation, iterations, progress=progress)
        for basis, exp_value in zip(["X", "Y", "Z"], exp_values):
            f = freqs[basis]
            if abs(f - exp_value) > epsilon:
                print(freqs, exp_values, epsilon)
                return False
        return True


class DebugConnection(BaseNetQASMConnection):

    node_ids: Dict[str, int] = {}

    def __init__(self, *args, **kwargs):
        """A connection that simply stores the subroutine it commits"""
        self.storage = []
        super().__init__(*args, **kwargs)

    @property
    def shared_memory(self) -> SharedMemory:
        return SharedMemory()

    def _commit_serialized_message(
        self, raw_msg: bytes, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        """Commit a message to the backend/qnodeos"""
        self.storage.append(raw_msg)

    def _get_network_info(self) -> Type[NetworkInfo]:
        return DebugNetworkInfo


class DebugNetworkInfo(NetworkInfo):
    @classmethod
    def _get_node_id(cls, node_name: str) -> int:
        """Returns the node id for the node with the given name"""
        node_id = DebugConnection.node_ids.get(node_name)
        if node_id is None:
            raise ValueError(f"{node_name} is not a known node name")
        return node_id

    @classmethod
    def _get_node_name(cls, node_id: int) -> str:
        """Returns the node name for the node with the given ID"""
        for n_name, n_id in DebugConnection.node_ids.items():
            if n_id == node_id:
                return n_name
        raise ValueError(f"{node_id} is not a known node ID")

    @classmethod
    def get_node_id_for_app(cls, app_name: str) -> int:
        """Returns the node id for the app with the given name"""
        return cls._get_node_id(node_name=app_name)

    @classmethod
    def get_node_name_for_app(cls, app_name: str) -> str:
        """Returns the node name for the app with the given name"""
        return app_name
