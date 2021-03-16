"""TODO write about connections"""

from __future__ import annotations

import abc
import logging
import os
import pickle
from itertools import count
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple, Type, Union

from qlink_interface import (
    EPRType,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerOKTypeR,
    RandomBasis,
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
from netqasm.lang.ir import BranchLabel, GenericInstr, ICmd, PreSubroutine
from netqasm.lang.ir2 import IrQbt, IrRotAxis, IrSingleGate, IrTwoGate
from netqasm.lang.parsing.text import assemble_subroutine
from netqasm.lang.subroutine import Subroutine
from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk.compiling import SubroutineCompiler
from netqasm.sdk.config import LogConfig
from netqasm.sdk.futures import Array, Future, RegFuture
from netqasm.sdk.network import NetworkInfo
from netqasm.sdk.qubit import Qubit, _FutureQubit
from netqasm.sdk.shared_memory import SharedMemory, SharedMemoryManager

from .builder import Builder, QubitHandle

T_Cmd = Union[ICmd, BranchLabel]
T_LinkLayerOkList = Union[
    List[LinkLayerOKTypeK], List[LinkLayerOKTypeM], List[LinkLayerOKTypeR]
]
T_Message = Union[Message, SubroutineMessage]
T_CValue = Union[int, Future, RegFuture]
T_PostRoutine = Callable[
    ["BaseNetQASMConnection2", Union[_FutureQubit, List[Future]], operand.Register],
    None,
]
T_BranchRoutine = Callable[["BaseNetQASMConnection2"], None]
T_LoopRoutine = Callable[["BaseNetQASMConnection2"], None]

if TYPE_CHECKING:
    from netqasm.sdk.epr_socket import EPRSocket


# NOTE this is needed to be able to instanciate tuples the same way as namedtuples
class _Tuple(tuple):
    @classmethod
    def __new__(cls, *args, **kwargs):
        return tuple.__new__(cls, args[1:])


class ConnectionManager:
    # Global dict to track all used app IDs for each program
    _APP_IDS: Dict[str, List[int]] = {}  # <party> -> [<app_id1>, <app_id2>, ...]

    # Dict[node_name, Dict[app_id, app_name]]
    _APP_NAMES: Dict[str, Dict[int, str]] = {}

    @classmethod
    def get_app_ids(cls) -> Dict[str, List[int]]:
        return cls._APP_IDS

    @classmethod
    def get_app_names(cls) -> Dict[str, Dict[int, str]]:
        return cls._APP_NAMES

    @classmethod
    def get_new_app_id(cls, name: str, app_id: Optional[int]) -> int:
        if name not in cls._APP_IDS:
            cls._APP_IDS[name] = []

        if app_id is None:
            for app_id in count(0):
                if app_id not in cls._APP_IDS[name]:
                    cls._APP_IDS[name].append(app_id)
                    return app_id
            raise RuntimeError("This should never be reached")
        else:
            if app_id in cls._APP_IDS[name]:
                raise ValueError("app_id={} is already in use".format(app_id))
            cls._APP_IDS[name].append(app_id)
            return app_id

    @classmethod
    def pop_app_id(cls, app_name: str, app_id: int) -> None:
        try:
            cls._APP_IDS[app_name].remove(app_id)
        except ValueError:
            pass  # Already removed


class BaseNetQASMConnection2(abc.ABC):
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
        self._app_id: int = ConnectionManager.get_new_app_id(app_name, app_id)

        if node_name is None:
            node_name = self.network_info.get_node_name_for_app(app_name)
        self._node_name: str = node_name

        self._shared_memory: Optional[
            SharedMemory
        ] = SharedMemoryManager.get_shared_memory(self.node_name, key=self._app_id)

        if log_config is None:
            log_config = LogConfig()

        # Should subroutines commited be saved for logging/debugging
        self._log_subroutines_dir: Optional[str] = log_config.log_subroutines_dir
        # Commited subroutines saved for logging/debugging
        self._commited_subroutines: List[Subroutine] = []

        self._logger: logging.Logger = get_netqasm_logger(
            f"{self.__class__.__name__}({self.app_name})"
        )

        if _init_app:
            self._init_new_app(max_qubits=max_qubits)

        if _setup_epr_sockets:
            # Setup epr sockets
            self._setup_epr_sockets(epr_sockets=epr_sockets)

        self._builder = Builder(app_name, node_name, app_id, max_qubits, epr_sockets)

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

    @property
    def builder(self) -> Builder:
        return self._builder

    def __str__(self):
        return (
            f"NetQASM connection for app '{self.app_name}' with node '{self.node_name}'"
        )

    def __enter__(self):
        """Used to open the connection in a context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def clear(self) -> None:
        ConnectionManager.pop_app_id(self.app_name, self.app_id)

    def close(self, clear_app: bool = True, stop_backend: bool = False) -> None:
        """Handle exiting of context."""
        # Flush all pending commands
        self.flush()

        ConnectionManager.pop_app_id(self.app_name, self.app_id)

        self._signal_stop(clear_app=clear_app, stop_backend=stop_backend)

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
            epr_socket.conn = self  # type: ignore
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

    def new_array(
        self, length: int = 1, init_values: Optional[List[Optional[int]]] = None
    ) -> Array:
        self._builder.new_array(length, init_values)
        # TODO convert ArrayHandle to Array
        return Array(self, length, 0)  # type: ignore

    def new_register(self, init_value: int = 0) -> RegFuture:
        self._builder.new_register(init_value)
        # TODO convert RegHandle to RegFuture
        return RegFuture(self)  # type: ignore

    def flush(self, block: bool = True, callback: Optional[Callable] = None) -> None:
        # subroutine = self._pop_pending_subroutine()
        # TODO
        subroutine = None
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
        subroutine = self._pre_process_subroutine(presubroutine)
        self._logger.info(f"Flushing compiled subroutine:\n{subroutine}")

        # Commit the subroutine to the quantum device
        self._commit_message(
            msg=SubroutineMessage(subroutine=subroutine),
            block=block,
            callback=callback,
        )

    def _subroutine_from_commands(self, commands: List[T_Cmd]) -> PreSubroutine:
        # Build sub-routine
        metadata = self._get_metadata()
        return PreSubroutine(**metadata, commands=commands)  # type: ignore

    def _get_metadata(self) -> Dict:
        return {
            "netqasm_version": NETQASM_VERSION,
            "app_id": self._app_id,
        }

    def _pre_process_subroutine(self, pre_subroutine: PreSubroutine) -> Subroutine:
        """Parses and assembles the subroutine.

        Can be subclassed and overried for more elaborate compiling.
        """
        subroutine: Subroutine = assemble_subroutine(pre_subroutine)
        # if self._compiler is not None:
        #     subroutine = self._compiler(subroutine=subroutine).compile()
        # if self._track_lines:
        #     self._log_subroutine(subroutine=subroutine)
        return subroutine

    def _log_subroutine(self, subroutine: Subroutine) -> None:
        self._commited_subroutines.append(subroutine)

    def block(self) -> None:
        """Block until flushed subroutines finish"""
        raise NotImplementedError

    def add_single_qubit_rotation_commands(
        self,
        instruction: GenericInstr,
        virtual_qubit_id: int,
        n: int = 0,
        d: int = 0,
        angle: Optional[float] = None,
    ) -> None:
        self._builder.q_rotate(IrRotAxis(name="Z"), QubitHandle(IrQbt()), angle=1.0)

    def add_single_qubit_commands(self, instr: GenericInstr, qubit_id: int) -> None:
        self._builder.q_gate(IrSingleGate(name="H"), QubitHandle(IrQbt()))

    def add_two_qubit_commands(
        self, instr: GenericInstr, control_qubit_id: int, target_qubit_id: int
    ) -> None:
        self._builder.q_two_gate(
            IrTwoGate(name="CNOT"), QubitHandle(IrQbt()), QubitHandle(IrQbt())
        )

    def add_measure_commands(
        self, qubit_id: int, future: Union[Future, RegFuture], inplace: bool
    ) -> None:
        self._builder.measure(QubitHandle(IrQbt()), False)

    def add_new_qubit_commands(self, qubit_id: int) -> None:
        self._builder.new_qubit()

    def add_init_qubit_commands(self, qubit_id: int) -> None:
        # TODO
        pass

    def add_qfree_commands(self, qubit_id: int) -> None:
        # TODO
        pass

    def create_epr(
        self,
        remote_node_id: int,
        epr_socket_id: int,
        number: int = 1,
        post_routine: Optional[T_PostRoutine] = None,
        sequential: bool = False,
        tp: EPRType = EPRType.K,
        random_basis_local: Optional[RandomBasis] = None,
        random_basis_remote: Optional[RandomBasis] = None,
        rotations_local: Tuple[int, int, int] = (0, 0, 0),
        rotations_remote: Tuple[int, int, int] = (0, 0, 0),
    ) -> Union[List[Qubit], T_LinkLayerOkList]:
        """Receives EPR pair with a remote node"""
        self._builder.epr_create_keep(EPRSocket("remote"))
        # TODO
        return [QubitHandle(IrQbt()) for _ in range(number)]

    def recv_epr(
        self,
        remote_node_id: int,
        epr_socket_id: int,
        number: int = 1,
        post_routine: Optional[T_PostRoutine] = None,
        sequential: bool = False,
        tp: EPRType = EPRType.K,
    ) -> Union[List[Qubit], T_LinkLayerOkList]:
        """Receives EPR pair with a remote node"""
        self._builder.epr_recv_keep(EPRSocket("remote"))
        # TODO
        return [QubitHandle(IrQbt()) for _ in range(number)]


class DebugConnection2(BaseNetQASMConnection2):

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
        return DebugNetworkInfo2


class DebugNetworkInfo2(NetworkInfo):
    @classmethod
    def _get_node_id(cls, node_name: str) -> int:
        """Returns the node id for the node with the given name"""
        node_id = DebugConnection2.node_ids.get(node_name)
        if node_id is None:
            raise ValueError(f"{node_name} is not a known node name")
        return node_id

    @classmethod
    def _get_node_name(cls, node_id: int) -> str:
        """Returns the node name for the node with the given ID"""
        for n_name, n_id in DebugConnection2.node_ids.items():
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
