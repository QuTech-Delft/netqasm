"""
Interface to quantum node controllers.

This module provides the `BaseNetQASMConnection` class which represents
the connection with a quantum node controller.
"""

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
    ContextManager,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

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
from netqasm.lang.ir import BreakpointAction, BreakpointRole, PreSubroutine
from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk.build_types import (
    GenericHardwareConfig,
    HardwareConfig,
    T_BranchRoutine,
    T_LoopRoutine,
)
from netqasm.sdk.compiling import SubroutineCompiler
from netqasm.sdk.config import LogConfig
from netqasm.sdk.futures import Array, Future, RegFuture, T_CValue
from netqasm.sdk.network import NetworkInfo
from netqasm.sdk.progress_bar import ProgressBar
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.shared_memory import SharedMemory, SharedMemoryManager
from netqasm.util.log import LineTracker

from .builder import Builder, SdkLoopUntilContext

# Generic type for messages sent to the quantum node controller.
# Note that `SubroutineMessage` does not derive from `Message` so it has to be
# mentioned explicitly.
T_Message = Union[Message, SubroutineMessage]

# Imports that are only needed for type checking
if TYPE_CHECKING:
    from netqasm.sdk import epr_socket as esck


class BaseNetQASMConnection(abc.ABC):
    """Base class for representing connections to a quantum node controller.

    A BaseNetQASMConnection instance provides an interface for Host programs to
    interact with a quantum node controller like QNodeOS, which controls the quantum
    hardware.

    The interaction with the quantum node controller includes registering applications,
    opening EPR sockets, sending NetQASM subroutines, and getting execution results,

    A BaseNetQASMConnection instance also provides a 'context' for the Host to
    run its code in. Code within this context is compiled into NetQASM subroutines
    and then sent to the quantum node controller.
    """

    # Global dict to track all used app IDs for each program
    _app_ids: Dict[str, List[int]] = {}  # <party> -> [<app_id1>, <app_id2>, ...]

    # Global dict to track app names per node.
    # Currently only used for logging purposes, specifically only in
    # `netqasm.runtime.process_logs._create_app_instr_logs`.
    # Dict[node_name, Dict[app_id, app_name]]
    _app_names: Dict[str, Dict[int, str]] = {}

    def __init__(
        self,
        app_name: str,
        node_name: Optional[str] = None,
        app_id: Optional[int] = None,
        max_qubits: int = 5,
        hardware_config: Optional[HardwareConfig] = None,
        log_config: LogConfig = None,
        epr_sockets: Optional[List[esck.EPRSocket]] = None,
        compiler: Optional[Type[SubroutineCompiler]] = None,
        return_arrays: bool = True,
        _init_app: bool = True,
        _setup_epr_sockets: bool = True,
    ):
        """BaseNetQASMConnection constructor.

        In most cases, you will want to instantiate a subclass of this.

        :param app_name: Name of the application.
            Specifically, this is the name of the program that runs on this particular
            node. So, `app_name` can often be seen as the name of the "role" within the
            multi-party application or protocol.
            For example, in a Blind Computation protocol, the two roles may be
            "client" and "server"; the `app_name` of a particular
            `BaseNetQASMConnection` instance may then e.g. be "client".

        :param node_name: name of the Node that is controlled by the quantum
            node controller that we connect to. The Node name may be different from
            the `app_name`, and e.g. reflect its geographical location, like a city
            name. If None, the Node name is obtained by querying the global
            `NetworkInfo` by using the `app_name`.

        :param app_id: ID of this application.
            An application registered in the quantum node controller using this
            connection will use this app ID.
            If None, a unique ID will be chosen (unique among possible other
            applications that were registered through other BaseNetQASMConnection
            instances).

        :param max_qubits: maximum number of qubits that can be in use
            at the same time by applications registered through this connection.
            Defaults to 5.

        :param hardware_config: configuration object with info about the underlying
            hardware. Used by the Builder of this Connection. When None,
            a generic configuration object is created with the default qubit count of 5.

        :param log_config: configuration object specifying what to log.

        :param epr_sockets: list of EPR sockets.
            If `_setup_epr_sockets` is True, these EPR sockets are automatically
            opened upon entering this connection's context.

        :param compiler: the class that is used to instantiate the compiler.
            If None, a compiler is used that can compile for the hardware of the
            node this connection is to.

        :param return_arrays: whether to add "return array"-instructions at the end
            of subroutines. A reason to set this to False could be that a quantum
            node controller does not support returning arrays back to the Host.

        :param _init_app: whether to immediately send a "register application" message
            to the quantum node controller upon construction of this connection.

        :param _setup_epr_sockets: whether to immediately send "open EPR socket"
            messages to the quantum node controller upon construction of this
            connection. If True, the "open EPR socket" messages are for the EPR sockets
            defined in the `epr_sockets` parameter.
        """
        self._app_name: str = app_name

        # Set the app ID. If one was provided in `app_id`, try to use that one.
        self._app_id: int = self._get_new_app_id(app_id)

        if node_name is None:
            node_name = self.network_info.get_node_name_for_app(app_name)
        self._node_name: str = node_name

        # Update global _app_names dict. Only used for logging purposes.
        if node_name not in self._app_names:
            self._app_names[node_name] = {}
        self._app_names[node_name][self._app_id] = app_name

        # Try to obtain the Shared Memory instance corresponding to this connection.
        # Depending on the runtime environment, this instance may not yet exist at
        # this moment. If this is the case, the SharedMemory instance *should*
        # become available later on.
        self._shared_memory: Optional[
            SharedMemory
        ] = SharedMemoryManager.get_shared_memory(self.node_name, key=self._app_id)

        # Whether to send additional closing messages to the quantum node controller
        # at the end of an application. See the `close()` method.
        # At the moment only used for debugging and not exposed to the user.
        self._clear_app_on_exit: bool = True
        self._stop_backend_on_exit: bool = True

        if log_config is None:
            log_config = LogConfig()

        self._line_tracker: LineTracker = LineTracker(log_config=log_config)
        self._track_lines: bool = log_config.track_lines

        # Set directory for storing serialized subroutines.
        self._log_subroutines_dir: Optional[str] = log_config.log_subroutines_dir

        if hardware_config is None:
            hardware_config = GenericHardwareConfig(max_qubits)

        # Builder object of this connection.
        # The Builder is used to gather application code and output an
        # Intermediate Representation (IR), which is then compiled into subroutines.
        self._builder = Builder(
            connection=self,
            app_id=self._app_id,
            hardware_config=hardware_config,
            compiler=compiler,
            return_arrays=return_arrays,
        )

        # What compiler (if any) to be used.
        # Currently, the "_compiler" attribute is more of a transpiler, since it can
        # only convert between NetQASM flavours.
        # The actual conversion from Python DSL statements to IR to NetQASM is
        # done by the Builder.
        self._compiler: Optional[Type[SubroutineCompiler]] = compiler

        # Logger for stdout. (Not for log files.)
        self._logger: logging.Logger = get_netqasm_logger(
            f"{self.__class__.__name__}({self.app_name})"
        )

        if _init_app:
            self._init_new_app(max_qubits=max_qubits)

        if _setup_epr_sockets:
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

    @app_id.setter
    def app_id(self, id: int) -> None:
        self._app_id = id
        self._builder.app_id = id

    @abc.abstractmethod
    def _get_network_info(self) -> Type[NetworkInfo]:
        raise NotImplementedError

    @property
    def network_info(self) -> Type[NetworkInfo]:
        return self._get_network_info()

    @property
    def builder(self) -> Builder:
        return self._builder

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
        """Start a context with this connection.

        Quantum operations specified within the connection are automatically compiled
        into NetQASM subroutines.
        These subroutines are sent to the quantum node controller, over this
        connection, when either :meth:`~.flush` is called or the connection goes out
        of context which calls :meth:`~.__exit__`.

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
                # Alternatively, this can be done by letting the connection
                # go out of context and move the print to after.
                alice.flush()
                print(m)
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Called automatically when a connection context ends.

        Default behavior is to call the `close` method on the connection.
        """
        # Allow to not clear the app or stop the backend upon exit, for debugging and post processing
        self.close(
            clear_app=self._clear_app_on_exit,
            stop_backend=self._stop_backend_on_exit,
        )

    def _get_new_app_id(self, app_id: Optional[int]) -> int:
        """Find a suitable new app ID.

        Tries to use the specified `app_id`, if not in use already.
        """
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
        """Remove the used app ID from the list."""
        try:
            self._app_ids[self.app_name].remove(self.app_id)
        except ValueError:
            pass  # Already removed

    def clear(self) -> None:
        self._pop_app_id()

    def close(self, clear_app: bool = True, stop_backend: bool = False) -> None:
        """Close a connection.

        By default, this method is automatically called when a connection context ends.
        """
        # Flush all pending commands
        self.flush()

        self._pop_app_id()

        self._signal_stop(clear_app=clear_app, stop_backend=stop_backend)
        self._builder.inactivate_qubits()

        if self._log_subroutines_dir is not None:
            self._save_log_subroutines()

    def _commit_message(
        self, msg: T_Message, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        """Commit a message to the quantum node controller.

        The message gets serialized and then sent through the connection.
        """
        self._logger.debug(f"Committing message {msg}")
        self._commit_serialized_message(
            raw_msg=bytes(msg), block=block, callback=callback
        )

    @abc.abstractmethod
    def _commit_serialized_message(
        self, raw_msg: bytes, block: bool = True, callback: Optional[Callable] = None
    ) -> None:
        """Commit a serialized message to the quantum node controller."""
        pass

    def _signal_stop(self, clear_app: bool = True, stop_backend: bool = True) -> None:
        """Signal to the quantum node controller to stop.

        This signal may be used with simulator backends so that they can e.g. reset
        their state.
        """
        if clear_app:
            self._commit_message(msg=StopAppMessage(app_id=self._app_id))

        if stop_backend:
            self._commit_message(msg=SignalMessage(signal=Signal.STOP), block=False)

    def _save_log_subroutines(self) -> None:
        """Serialize and dump subroutines that were sent over this connection."""
        filename = f"subroutines_{self.app_name}.pkl"
        filepath = os.path.join(self._log_subroutines_dir, filename)  # type: ignore
        with open(filepath, "wb") as f:
            pickle.dump(self._builder.committed_subroutines, f)

    @property
    def shared_memory(self) -> SharedMemory:
        """Get this connection's Shared Memory object.

        This property should *not* be accessed before any potential setting-up
        of shared memories has finished. If it cannot be found, an error is raised.
        """
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

    @property
    def active_qubits(self) -> List[Qubit]:
        """Get a list of qubits that are currently in use.

        "In use" means that the virtual qubit represented by this `Qubit` instance
        has been allocated and hence its virtual ID cannot be re-used.

        :return: list of active qubits
        """
        return self._builder._mem_mgr.get_active_qubits()

    def _init_new_app(self, max_qubits: int) -> None:
        """Send a message to the quantum node controller to register a new application.

        :param max_qubits: maximum number of qubits that this application may allocate
            at the same time.
        """
        self._commit_message(
            msg=InitNewAppMessage(
                app_id=self._app_id,
                max_qubits=max_qubits,
            )
        )

        # Wait until a shared memory is available.
        # This is to be sure that we can access the shared memory at any time
        # during the application.
        # TODO: improve how this is handled
        while self.shared_memory is None:
            pass

    def _setup_epr_sockets(self, epr_sockets: Optional[List[esck.EPRSocket]]) -> None:
        """Send messages to the quantum node controller to open EPR sockets."""
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
        """Send a message to the quantum node controller to open an EPR socket."""
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
        """Compile and send all pending operations to the quantum node controller.

        All operations that have been added to this connection's Builder (typically by
        issuing these operations within a connection context) are collected and
        compiled into a NetQASM subroutine. This subroutine is then sent over the connection
        to be executed by the quantum node controller.

        :param block: block on receiving the result of executing the compiled subroutine
            from the quantum node controller.
        :param callback: if `block` is False, this callback is called when the quantum
            node controller sends the subroutine results.
        """
        subroutine = self._builder.subrt_pop_pending_subroutine()
        if subroutine is None:
            return

        self.commit_subroutine(
            presubroutine=subroutine,
            block=block,
            callback=callback,
        )

    def commit_subroutine(
        self,
        presubroutine: PreSubroutine,
        block: bool = True,
        callback: Optional[Callable] = None,
    ) -> None:
        """Send a subroutine to the quantum node controller.

        Takes a `PreSubroutine`, i.e. an intermediate representation of the subroutine
        that comes from the Builder.
        The PreSubroutine is compiled into a `Subroutine` instance.
        """
        self._logger.debug(f"Flushing presubroutine:\n{presubroutine}")

        # Parse, assembly and possibly compile the subroutine
        subroutine = self._builder.subrt_compile_subroutine(presubroutine)
        self._logger.info(f"Flushing compiled subroutine:\n{subroutine}")

        # Commit the subroutine to the quantum device
        self._commit_message(
            msg=SubroutineMessage(subroutine=subroutine),
            block=block,
            callback=callback,
        )

        self._builder._reset()

    def block(self) -> None:
        """Block until a flushed subroutines finishes.

        This should be implemented by subclasses.

        :raises NotImplementedError
        """
        raise NotImplementedError

    def new_array(
        self, length: int = 1, init_values: Optional[List[Optional[int]]] = None
    ) -> Array:
        """Allocate a new array in the shared memory.

        This operation is handled by the connection's Builder.
        The Builder make sures the relevant NetQASM instructions end up in the
        subroutine.

        :param length: length of the array, defaults to 1
        :param init_values: list of initial values of the array. If not None, must
            have the same length as `length`.
        :return: a handle to the array that can be used in application code
        """
        return self._builder.alloc_array(length, init_values)

    def loop(
        self,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[operand.Register] = None,
    ) -> ContextManager[operand.Register]:
        """Create a context for code that gets looped.

        Each iteration of the loop is associated with an index, which starts at 0
        by default. Each iteration the index is increased by `step` (default 1).
        Looping stops when the index reaches `stop`.

        Code inside the context *must* be compilable to NetQASM, that is,
        it should only contain quantum operations and/or classical values that are
        are stored in shared memory (arrays and registers).
        No classical communication is allowed.

        This operation is handled by the connection's Builder.
        The Builder make sures the NetQASM subroutine contains a loop around the
        (compiled) code that is inside the context.

        Example:

        .. code-block::

            with NetQASMConnection(app_name="alice") as alice:
                outcomes = alice.new_array(10)
                with alice.loop(10) as i:
                    q = Qubit(alice)
                    q.H()
                    outcome = outcomes.get_future_index(i)
                    q.measure(outcome)

        :param stop: end of iteration range (exluding)
        :param start: start of iteration range (including), defaults to 0
        :param step: step size of iteration range, defaults to 1
        :param loop_register: specific register to be used for holding the loop index.
            In most cases there is no need to explicitly specify this.
        :return: the context object (to be used in a `with ...` expression)
        """
        return self._builder.sdk_loop_context(stop, start, step, loop_register)

    def loop_body(
        self,
        body: T_LoopRoutine,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[Union[operand.Register, str]] = None,
    ) -> None:
        """Loop code that is defined in a Python function (body).

        The function to loop should have a single argument with that has the
        `BaseNetQASMConnection` type.

        :param body: function to loop
        :param stop: end of iteration range (exluding)
        :param start: start of iteration range (including), defaults to 0
        :param step: step size of iteration range, defaults to 1
        :param loop_register: specific register to be used for holding the loop index.
        """
        self._builder.sdk_loop_body(body, stop, start, step, loop_register)

    def loop_until(self, max_iterations: int) -> ContextManager[SdkLoopUntilContext]:
        """Create a context with code to be looped until the exit condition is met, or
        the maximum number of tries has been reached.

        The code inside the context is automatically looped (re-run).
        At the end of each iteration, the exit_condition of the context object is
        checked. If the condition holds, the loop exits. Otherwise the loop
        does another iteration. If `max_iterations` iterations have been reached,
        the loop exits anyway.

        Make sure you set the loop_condition on the context object, like e.g.

        .. code-block::

        with connection.loop_until(max_iterations=10) as loop:
            q = Qubit(conn)
            m = q.measure()
            constraint = ValueAtMostConstraint(m, 0)
            loop.set_exit_condition(constraint)


        :param max_iterations: the maximum number of times to loop
        """
        return self.builder.sdk_new_loop_until_context(max_iterations)

    def if_eq(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """Execute a function if a == b.

        Code inside the callback function *must* be compilable to NetQASM, that is,
        it should only contain quantum operations and/or classical values that are
        are stored in shared memory (arrays and registers).
        No classical communication is allowed.

        :param a: a classical value
        :param b: a classical value
        :param body: function to execute if condition is true
        """
        self._builder.sdk_if_eq(a, b, body)

    def if_ne(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """Execute a function if a != b.

        Code inside the callback function *must* be compilable to NetQASM, that is,
        it should only contain quantum operations and/or classical values that are
        are stored in shared memory (arrays and registers).
        No classical communication is allowed.

        :param a: a classical value
        :param b: a classical value
        :param body: function to execute if condition is true
        """
        self._builder.sdk_if_ne(a, b, body)

    def if_lt(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """Execute a function if a < b.

        Code inside the callback function *must* be compilable to NetQASM, that is,
        it should only contain quantum operations and/or classical values that are
        are stored in shared memory (arrays and registers).
        No classical communication is allowed.

        :param a: a classical value
        :param b: a classical value
        :param body: function to execute if condition is true
        """
        self._builder.sdk_if_lt(a, b, body)

    def if_ge(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """Execute a function if a > b.

        Code inside the callback function *must* be compilable to NetQASM, that is,
        it should only contain quantum operations and/or classical values that are
        are stored in shared memory (arrays and registers).
        No classical communication is allowed.

        :param a: a classical value
        :param b: a classical value
        :param body: function to execute if condition is true
        """
        self._builder.sdk_if_ge(a, b, body)

    def if_ez(self, a: T_CValue, body: T_BranchRoutine) -> None:
        """Execute a function if a == 0.

        Code inside the callback function *must* be compilable to NetQASM, that is,
        it should only contain quantum operations and/or classical values that are
        are stored in shared memory (arrays and registers).
        No classical communication is allowed.

        :param a: a classical value
        :param body: function to execute if condition is true
        """
        self._builder.sdk_if_ez(a, body)

    def if_nz(self, a: T_CValue, body: T_BranchRoutine) -> None:
        """Execute a function if a != 0.

        Code inside the callback function *must* be compilable to NetQASM, that is,
        it should only contain quantum operations and/or classical values that are
        are stored in shared memory (arrays and registers).
        No classical communication is allowed.

        :param a: a classical value
        :param body: function to execute if condition is true
        """
        self._builder.sdk_if_nz(a, body)

    def try_until_success(self, max_tries: int = 1) -> ContextManager[None]:
        """TODO docstring"""
        return self._builder.sdk_try_context(max_tries)

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

    def insert_breakpoint(
        self, action: BreakpointAction, role: BreakpointRole = BreakpointRole.CREATE
    ) -> None:
        self._builder._build_cmds_breakpoint(action, role)


class DebugConnection(BaseNetQASMConnection):
    """Connection that mocks most of the `BaseNetQASMConnection` logic.

    Subroutines that are flushed are simply stored in this object.
    No actual connection is made.
    """

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
