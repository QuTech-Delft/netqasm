"""
NetQASM execution interface for simulators.

This module provides the `Executor` class which can be used by simulators
as a base class for executing NetQASM instructions.
"""

from __future__ import annotations

import logging
import os
import traceback
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from itertools import count
from types import GeneratorType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

import numpy as np
import qlink_interface as qlink_1_0

from netqasm.backend.network_stack import OK_FIELDS_K as OK_FIELDS
from netqasm.backend.network_stack import BaseNetworkStack
from netqasm.lang import instr as ins
from netqasm.lang import operand
from netqasm.lang.encoding import RegisterName
from netqasm.lang.instr.base import NetQASMInstruction
from netqasm.lang.operand import Address, ArrayEntry, ArraySlice
from netqasm.lang.parsing import parse_address
from netqasm.logging.glob import get_netqasm_logger
from netqasm.logging.output import InstrLogger
from netqasm.qlink_compat import (
    LinkLayerCreate,
    LinkLayerErr,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerOKTypeR,
    RequestType,
    ReturnType,
    get_creator_node_id,
    response_from_qlink_1_0,
)
from netqasm.sdk import shared_memory
from netqasm.sdk.shared_memory import Arrays, SharedMemory, SharedMemoryManager
from netqasm.util.error import NotAllocatedError

# Imports that are only needed for type checking
if TYPE_CHECKING:
    from netqasm.lang import subroutine as subrt_module

# Type definitions
T_UnitModule = List[Optional[int]]
T_LinkLayerResponse = Union[
    LinkLayerOKTypeK, LinkLayerOKTypeM, LinkLayerOKTypeR, LinkLayerErr
]
T_LinkLayerResponseOK = Union[LinkLayerOKTypeK, LinkLayerOKTypeM, LinkLayerOKTypeR]

T_RequestKey = Tuple[int, int]


@dataclass
class EprCmdData:
    """Container for info about EPR pending requests."""

    subroutine_id: int
    ent_results_array_address: int
    q_array_address: Optional[int]
    request: Optional[LinkLayerCreate]
    tot_pairs: int
    pairs_left: int


def inc_program_counter(method):
    """Decorator that automatically increases the current program counter.

    Should be used on functions that interpret a single NetQASM instruction.
    """

    def new_method(self, subroutine_id, instr):
        output = method(self, subroutine_id, instr)
        if isinstance(output, GeneratorType):
            output = yield from output
        self._program_counters[subroutine_id] += 1
        return output

    new_method.__name__ == method.__name__
    return new_method


class Executor:
    """Base class for entities that execute NetQASM applications.

    An Executor represents the component in a quantum node controller that handles
    the registration and execution of NetQASM applications.
    It can execute NetQASM subroutines by interpreting their instructions.

    This base class provides handlers for classical NetQASM instructions.
    These are methods with names `_instr_XXX`.
    Methods that handle quantum instructions are a no-op and should be overridden
    by subclasses.
    Entanglement instructions are handled and forwarded to the network stack.
    """

    # Global dictionary holding instruction logger objects per Executor instance
    _INSTR_LOGGERS: Dict[str, Optional[InstrLogger]] = {}

    # Class used for instruction loggers. May be different for subclasses of `Executor`.
    instr_logger_class = InstrLogger

    def __init__(
        self,
        name: Optional[str] = None,
        instr_log_dir: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Executor constructor.

        :param name: name of the executor for logging purposes, defaults to None
        :param instr_log_dir: directory to log instructions to, defaults to None
        """
        self._name: str  # declare type

        if name is None:
            self._name = f"{self.__class__}"
        else:
            self._name = name

        self._instruction_handlers: Dict[
            str, Callable
        ] = self._get_instruction_handlers()

        # Registers for different apps
        self._registers: Dict[int, Dict[RegisterName, shared_memory.RegisterGroup]] = {}

        # Arrays stored in memory for different apps
        self._app_arrays: Dict[int, Arrays] = {}

        # Shared memory with host for different apps
        self._shared_memories: Dict[int, SharedMemory] = {}

        self._qubit_unit_modules: Dict[int, T_UnitModule] = {}

        # There will be seperate program counters for each subroutine
        self._program_counters: Dict[int, int] = defaultdict(int)

        # Keep track of what subroutines are currently handled
        self._subroutines: Dict[int, subrt_module.Subroutine] = {}

        # Keep track of which subroutine in the order
        self._next_subroutine_id: int = 0

        # Keep track of what physical qubit addresses are in use
        self._used_physical_qubit_addresses: Set[int] = set()

        # Keep track of the create epr requests in progress
        self._epr_create_requests: Dict[T_RequestKey, List[EprCmdData]] = defaultdict(
            list
        )

        # Keep track of the recv epr requests in progress
        self._epr_recv_requests: Dict[T_RequestKey, List[EprCmdData]] = defaultdict(
            list
        )

        # Handle responsed for entanglement generation
        self._epr_response_handlers: Dict[
            ReturnType, Callable
        ] = self._get_epr_response_handlers()

        # Keep track of pending epr responses to handle
        self._pending_epr_responses: List[T_LinkLayerResponse] = []

        # Network stack
        self._network_stack: Optional[BaseNetworkStack] = None

        self._instr_logger: Optional[InstrLogger]  # declare type

        # Logger for instructions
        if instr_log_dir is None:
            self._instr_logger = None
        else:
            self._instr_logger = self.__class__.get_instr_logger(
                node_name=self._name,
                instr_log_dir=instr_log_dir,
                executor=self,
            )

        # Logger
        self._logger: logging.Logger = get_netqasm_logger(
            f"{self.__class__.__name__}({self._name})"
        )

    @property
    def name(self) -> str:
        """Get the name of this executor.

        :return: name
        """
        return self._name

    @property
    def node_id(self) -> int:
        """Get the ID of the node this Executor runs on

        :raises NotImplementedError: This should be overridden by a subclass
        :return: ID of the node
        """
        raise NotImplementedError

    def set_instr_logger(self, instr_log_dir: str) -> None:
        """Let the executor use an instruction logger that logs to `instr_log_dir`

        :param instr_log_dir: path to the log directory
        """
        self._instr_logger = self.__class__.get_instr_logger(
            node_name=self._name,
            instr_log_dir=instr_log_dir,
            executor=self,
            force_override=True,
        )

    @classmethod
    def get_instr_logger(
        cls,
        node_name: str,
        instr_log_dir: str,
        executor: Executor,
        force_override: bool = False,
    ) -> InstrLogger:
        instr_logger = cls._INSTR_LOGGERS.get(node_name)
        if instr_logger is None or force_override:
            filename = f"{str(node_name).lower()}_instrs.yaml"
            filepath = os.path.join(instr_log_dir, filename)
            instr_logger = cls.instr_logger_class(
                filepath=filepath,
                executor=executor,
            )
            cls._INSTR_LOGGERS[node_name] = instr_logger
        return instr_logger

    def _get_simulated_time(self) -> int:
        return 0

    @property
    def network_stack(self) -> Optional[BaseNetworkStack]:
        """Get the network stack (if any) connected to this Executor.

        :return: the network stack
        """
        return self._network_stack

    @network_stack.setter
    def network_stack(self, network_stack: BaseNetworkStack) -> None:
        if not isinstance(network_stack, BaseNetworkStack):
            raise TypeError(
                f"network_stack must be an instance of BaseNetworkStack, not {type(network_stack)}"
            )
        self._network_stack = network_stack

    def init_new_application(self, app_id: int, max_qubits: int) -> None:
        """Register a new application.

        :param app_id: App ID of the application.
        :param max_qubits: Maximum number of qubits the application is allowed to
            allocate at the same time.
        """
        self.allocate_new_qubit_unit_module(app_id=app_id, num_qubits=max_qubits)
        self._setup_registers(app_id=app_id)
        self._setup_arrays(app_id=app_id)
        self._new_shared_memory(app_id=app_id)

    def _setup_registers(self, app_id: int) -> None:
        """Setup registers for application"""
        self._registers[app_id] = shared_memory.setup_registers()

    def _setup_arrays(self, app_id: int) -> None:
        """Setup memory for storing arrays for application"""
        self._app_arrays[app_id] = Arrays()

    def _new_shared_memory(self, app_id: int) -> None:
        """Instantiate a new shared memory with an application"""
        self._shared_memories[app_id] = SharedMemoryManager.create_shared_memory(
            node_name=self._name, key=app_id
        )

    def setup_epr_socket(
        self, epr_socket_id: int, remote_node_id: int, remote_epr_socket_id: int
    ) -> Generator[Any, None, None]:
        """Instruct the Executor to open an EPR Socket.

        The Executor forwards this instruction to the Network Stack.

        :param epr_socket_id: ID of local EPR socket
        :param remote_node_id: ID of remote node
        :param remote_epr_socket_id: ID of remote EPR socket
        :yield: [description]
        """
        if self.network_stack is None:
            return
        output = self.network_stack.setup_epr_socket(
            epr_socket_id=epr_socket_id,
            remote_node_id=remote_node_id,
            remote_epr_socket_id=remote_epr_socket_id,
        )
        if isinstance(output, GeneratorType):
            yield from output

    def stop_application(self, app_id: int) -> Generator[Any, None, None]:
        """Stop an application and clear all qubits and classical memories.

        :param app_id: ID of the application to stop
        :yield: [description]
        """
        yield from self._clear_qubits(app_id=app_id)
        self._clear_registers(app_id=app_id)
        self._clear_arrays(app_id=app_id)
        self._clear_shared_memory(app_id=app_id)

    def _clear_qubits(self, app_id: int) -> Generator[Any, None, None]:
        unit_module = self._qubit_unit_modules.pop(app_id)
        for virtual_address, physical_address in enumerate(unit_module):
            if physical_address is None:
                continue
            self._used_physical_qubit_addresses.remove(physical_address)
            output = self._clear_phys_qubit_in_memory(physical_address)
            if isinstance(output, GeneratorType):
                yield from output

    def _clear_registers(self, app_id: int) -> None:
        self._registers.pop(app_id)

    def _clear_arrays(self, app_id: int) -> None:
        self._app_arrays.pop(app_id)

    def _clear_shared_memory(self, app_id: int) -> None:
        self._shared_memories.pop(app_id)

    def _reset_program_counter(self, subroutine_id: int) -> None:
        """Resets the program counter for a given subroutine ID"""
        self._program_counters.pop(subroutine_id, 0)

    def _clear_subroutine(self, subroutine_id: int) -> None:
        """Clears a subroutine from the executor"""
        self._reset_program_counter(subroutine_id=subroutine_id)
        self._subroutines.pop(subroutine_id, 0)

    def _get_instruction_handlers(self) -> Dict[str, Callable]:
        """Creates the dictionary of instruction handlers"""

        # For these core instructions, we provide a direct "_instr_{name}" method
        # The other types are handled in _execute_command
        mnemonic_mapping = [
            "qalloc",
            "array",
            "set",
            "store",
            "load",
            "undef",
            "lea",
            "meas",
            "create_epr",
            "recv_epr",
            "wait_all",
            "wait_any",
            "wait_single",
            "qfree",
            "ret_reg",
            "ret_arr",
        ]
        instruction_handlers = {
            mne: getattr(self, f"_instr_{mne}") for mne in mnemonic_mapping
        }
        return instruction_handlers

    def _get_epr_response_handlers(self) -> Dict[ReturnType, Callable]:
        """Get callbacks for EPR generation responses from the Network Stack.

        :return: dictionary of callbacks for each response type
        """
        epr_response_handlers = {
            ReturnType.ERR: self._handle_epr_err_response,
            ReturnType.OK_K: self._handle_epr_ok_k_response,
            ReturnType.OK_M: self._handle_epr_ok_m_response,
            ReturnType.OK_R: self._handle_epr_ok_r_response,
        }  # type: Dict[ReturnType, Callable]

        return epr_response_handlers

    def consume_execute_subroutine(self, subroutine: subrt_module.Subroutine) -> None:
        """Consume the generator returned by `execute_subroutine`.

        :param subroutine: subroutine to execute
        """
        list(self.execute_subroutine(subroutine=subroutine))

    def execute_subroutine(
        self, subroutine: subrt_module.Subroutine
    ) -> Generator[Any, None, None]:
        """Execute a NetQASM subroutine.

        This is a generator to allow simulators to yield at certain points during execution,
        e.g. to yield control to a asynchronous runtime.

        :param subroutine: subroutine to execute
        :yield: [description]
        """
        subroutine_id = self._get_new_subroutine_id()
        self._subroutines[subroutine_id] = subroutine
        self._reset_program_counter(subroutine_id)
        output = self._execute_commands(subroutine_id, subroutine.commands)
        if isinstance(output, GeneratorType):
            yield from output
        self._clear_subroutine(subroutine_id=subroutine_id)

    def _get_new_subroutine_id(self) -> int:
        self._next_subroutine_id += 1
        return self._next_subroutine_id - 1

    def _execute_commands(
        self, subroutine_id: int, commands: List[NetQASMInstruction]
    ) -> Generator[Any, None, None]:
        """Execute a sequence of NetQASM instructions (commands) that are
        in a subroutine.

        :param subroutine_id: ID of the subroutine these instructions are in
        :param commands: list of NetQASM instructions
        :yield: [description]
        """
        while self._program_counters[subroutine_id] < len(commands):
            prog_counter = self._program_counters[subroutine_id]
            command = commands[prog_counter]
            try:
                output = self._execute_command(subroutine_id, command)
                if isinstance(
                    output, GeneratorType
                ):  # sanity check: should always be the case
                    yield from output
            except Exception as exc:
                traceback_str = "".join(traceback.format_tb(exc.__traceback__))
                self._handle_command_exception(exc, prog_counter, traceback_str)
                break

    def _handle_command_exception(
        self, exc: Exception, prog_counter: int, traceback_str: str
    ) -> None:
        raise exc.__class__(f"At line {prog_counter}: {exc}\n{traceback_str}") from exc

    def _execute_command(
        self, subroutine_id: int, command: NetQASMInstruction
    ) -> Generator[Any, None, None]:
        """Execute a single NetQASM instruction (command).

        :raises TypeError: if `command` is not a NetQASMInstruction
        :raises RuntimeError: if something went wrong while interpreting the
        instruction
        :yield: [description]
        """
        if not isinstance(command, NetQASMInstruction):
            raise TypeError(f"Expected a NetQASMInstruction, not {type(command)}")

        prog_counter = self._program_counters[subroutine_id]

        output = None
        if command.mnemonic in self._instruction_handlers:
            output = self._instruction_handlers[command.mnemonic](
                subroutine_id, command
            )
        else:
            if (
                isinstance(command, ins.core.SingleQubitInstruction)
                or isinstance(command, ins.core.InitInstruction)
                or isinstance(command, ins.core.QAllocInstruction)
                or isinstance(command, ins.core.QFreeInstruction)
            ):
                output = self._handle_single_qubit_instr(subroutine_id, command)
            elif isinstance(command, ins.core.TwoQubitInstruction):
                output = self._handle_two_qubit_instr(subroutine_id, command)
            elif isinstance(command, ins.core.RotationInstruction):
                output = self._handle_single_qubit_rotation(subroutine_id, command)
            elif isinstance(command, ins.core.ControlledRotationInstruction):
                output = self._handle_controlled_qubit_rotation(subroutine_id, command)
            elif (
                isinstance(command, ins.core.JmpInstruction)
                or isinstance(command, ins.core.BranchUnaryInstruction)
                or isinstance(command, ins.core.BranchBinaryInstruction)
            ):
                self._handle_branch_instr(subroutine_id, command)
            elif isinstance(command, ins.core.ClassicalOpInstruction) or isinstance(
                command, ins.core.ClassicalOpModInstruction
            ):
                output = self._handle_binary_classical_instr(subroutine_id, command)
            else:
                raise RuntimeError(f"unknown instr type: {type(command)}")

        if isinstance(output, GeneratorType):
            output = yield from output
        if self._instr_logger is not None:
            self._instr_logger.log(
                subroutine_id=subroutine_id,
                app_id=self._get_app_id(subroutine_id),
                command=command,
                output=output,
                program_counter=prog_counter,
            )

    @inc_program_counter
    def _instr_set(self, subroutine_id: int, instr: ins.core.SetInstruction) -> None:
        """Handle a NetQASM 'set' instruction."""
        self._logger.debug(f"Set register {instr.reg} to {instr.imm}")
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._set_register(app_id, instr.reg, instr.imm.value)

    def _set_register(
        self, app_id: int, register: operand.Register, value: int
    ) -> None:
        """Set the value of a register."""
        self._registers[app_id][register.name][register.index] = value

    def _get_register(self, app_id: int, register: operand.Register) -> Optional[int]:
        return self._registers[app_id][register.name][register.index]

    @inc_program_counter
    def _instr_qalloc(
        self, subroutine_id: int, instr: ins.core.QAllocInstruction
    ) -> int:
        """Handle a NetQASM `qalloc` instruction.

        :return: ID of physical qubit that got allocated
        """
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        qubit_address = self._get_register(app_id, instr.reg)
        if qubit_address is None:
            raise RuntimeError(f"qubit address in register {instr.reg} is not defined")
        self._logger.debug(f"Taking qubit at address {qubit_address}")
        return self._allocate_physical_qubit(subroutine_id, qubit_address)

    @inc_program_counter
    def _instr_store(
        self, subroutine_id: int, instr: ins.core.StoreInstruction
    ) -> None:
        """Handle a NetQASM `store` instruction.

        Updates the relevant array entry.
        """
        register = instr.reg
        array_entry = instr.entry
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        value = self._get_register(app_id, register)
        if value is None:
            raise RuntimeError(f"value in register {register} is not defined")
        self._logger.debug(
            f"Storing value {value} from register {register} to array entry {array_entry}"
        )
        self._set_array_entry(app_id=app_id, array_entry=array_entry, value=value)

    @inc_program_counter
    def _instr_load(self, subroutine_id: int, instr: ins.core.LoadInstruction) -> None:
        """Handle a NetQASM `load` instruction.

        Loads the relevant array entry into a register.
        """
        register = instr.reg
        array_entry = instr.entry
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        value = self._get_array_entry(app_id=app_id, array_entry=array_entry)
        if value is None:
            raise RuntimeError(f"array value at {array_entry} is not defined")
        self._logger.debug(
            f"Storing value {value} from array entry {array_entry} to register {register}"
        )
        self._set_register(app_id, register, value)

    @inc_program_counter
    def _instr_lea(self, subroutine_id: int, instr: ins.core.LeaInstruction) -> None:
        """Handle a NetQASM `lea` instruction."""
        register = instr.reg
        address = instr.address
        self._logger.debug(f"Storing address of {address} to register {register}")
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._set_register(app_id=app_id, register=register, value=address.address)

    @inc_program_counter
    def _instr_undef(
        self, subroutine_id: int, instr: ins.core.UndefInstruction
    ) -> None:
        """Handle a NetQASM `undef` instruction.

        Sets the relevant array entry to `None`.
        """
        array_entry = instr.entry
        self._logger.debug(f"Unset array entry {array_entry}")
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._set_array_entry(app_id=app_id, array_entry=array_entry, value=None)

    @inc_program_counter
    def _instr_array(
        self, subroutine_id: int, instr: ins.core.ArrayInstruction
    ) -> None:
        """Handle a NetQASM `array` instruction.

        Instantiates a new array with the relevant length.
        """
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        length = self._get_register(app_id, instr.size)
        assert length is not None
        address = instr.address
        self._logger.debug(
            f"Initializing an array of length {length} at address {address}"
        )
        self._initialize_array(app_id=app_id, address=address, length=length)

    def _initialize_array(self, app_id: int, address: Address, length: int) -> None:
        arrays = self._app_arrays[app_id]
        arrays.init_new_array(address.address, length)

    def _handle_branch_instr(
        self,
        subroutine_id: int,
        instr: Union[
            ins.core.BranchUnaryInstruction,
            ins.core.BranchBinaryInstruction,
            ins.core.JmpInstruction,
        ],
    ) -> None:
        """Handle a NetQASM branching instruction.

        The program counter is updated to the target label (in case of a jump)
        or to the next instruction (no jump).
        """
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        a, b = None, None
        registers = []
        if isinstance(instr, ins.core.BranchUnaryInstruction):
            a = self._get_register(app_id=app_id, register=instr.reg)
            registers = [instr.reg]
        elif isinstance(instr, ins.core.BranchBinaryInstruction):
            a = self._get_register(app_id=app_id, register=instr.reg0)
            b = self._get_register(app_id=app_id, register=instr.reg1)
            registers = [instr.reg0, instr.reg1]

        if isinstance(instr, ins.core.JmpInstruction):
            condition = True
        elif isinstance(instr, ins.core.BranchUnaryInstruction):
            condition = instr.check_condition(a)
        elif isinstance(instr, ins.core.BranchBinaryInstruction):
            condition = instr.check_condition(a, b)

        if condition:
            jump_address = instr.line
            self._logger.debug(
                f"Branching to line {jump_address}, since {instr}(a={a}, b={b}) "
                f"is True, with values from registers {registers}"
            )
            self._program_counters[subroutine_id] = jump_address.value
        else:
            self._logger.debug(
                f"Don't branch, since {instr}(a={a}, b={b}) "
                f"is False, with values from registers {registers}"
            )
            self._program_counters[subroutine_id] += 1

    @inc_program_counter
    def _handle_binary_classical_instr(
        self,
        subroutine_id: int,
        instr: Union[
            ins.core.ClassicalOpInstruction,
            ins.core.ClassicalOpModInstruction,
        ],
    ) -> None:
        """Handle a NetQASM branching instruction with a binary condition."""
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        mod = None
        if isinstance(instr, ins.core.ClassicalOpModInstruction):
            mod = self._get_register(app_id=app_id, register=instr.regmod)
        if mod is not None and mod < 1:
            raise RuntimeError(f"Modulus needs to be greater or equal to 1, not {mod}")
        a = self._get_register(app_id=app_id, register=instr.regin0)
        b = self._get_register(app_id=app_id, register=instr.regin1)
        assert a is not None
        assert b is not None
        value = self._compute_binary_classical_instr(instr, a, b, mod=mod)
        mod_str = "" if mod is None else f"(mod {mod})"
        self._logger.debug(
            f"Performing {instr} of a={a} and b={b} {mod_str} "
            f"and storing the value {value} at register {instr.regout}"
        )
        self._set_register(app_id=app_id, register=instr.regout, value=value)

    def _compute_binary_classical_instr(
        self, instr: NetQASMInstruction, a: int, b: int, mod: Optional[int] = 1
    ):
        """Evaluate the binary condition of a NetQASM branching instruction."""
        if isinstance(instr, ins.core.AddInstruction):
            return a + b
        elif isinstance(instr, ins.core.AddmInstruction):
            assert mod is not None
            return (a + b) % mod
        elif isinstance(instr, ins.core.SubInstruction):
            return a - b
        elif isinstance(instr, ins.core.SubmInstruction):
            assert mod is not None
            return (a - b) % mod
        else:
            raise ValueError(f"{instr} cannot be used as binary classical function")

    @inc_program_counter
    def _handle_single_qubit_instr(
        self, subroutine_id: int, instr: ins.core.SingleQubitInstruction
    ) -> Generator[Any, None, None]:
        """Handle a single-qubit NetQASM instruction.

        Gets the virtual ID of the qubit and then calls `_do_single_qubit_instr`.

        This is a generator so that implementations of `_do_single_qubit_instr` can
        be generators themselves.
        """
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address = self._get_register(app_id=app_id, register=instr.reg)
        assert q_address is not None
        self._logger.debug(f"Performing {instr} on the qubit at address {q_address}")
        output = self._do_single_qubit_instr(instr, subroutine_id, q_address)
        if isinstance(output, GeneratorType):
            yield from output

    def _do_single_qubit_instr(
        self, instr: ins.core.SingleQubitInstruction, subroutine_id: int, address: int
    ) -> Optional[Generator[Any, None, None]]:
        """Perform a single qubit gate on qubit with virtual ID `address`.

        This is a generator to allow simulators to yield at certain points during
        execution, e.g. to yield control to an asynchronous runtime.

        :param instr: NetQASM instruction to execute
        :param subroutine_id: ID of subroutine currently being executed
        :param address: virtual ID of qubit to act on
        :return: [description]
        """
        return None

    @inc_program_counter
    def _handle_single_qubit_rotation(
        self, subroutine_id: int, instr: ins.core.RotationInstruction
    ) -> Generator[Any, None, None]:
        """Handle a single-qubit NetQASM rotation instruction.

        Gets the virtual ID of the qubit and then calls `_do_single_qubit_rotation`.

        This is a generator so that implementations of `_do_single_qubit_rotation` can
        be generators themselves.
        """
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address = self._get_register(app_id=app_id, register=instr.reg)
        assert q_address is not None
        angle = self._get_rotation_angle_from_operands(
            app_id=app_id,
            n=instr.angle_num.value,
            d=instr.angle_denom.value,
        )
        self._logger.debug(
            f"Performing {instr} with angle {angle} "
            f"on the qubit at address {q_address}"
        )
        output = self._do_single_qubit_rotation(
            instr, subroutine_id, q_address, angle=angle
        )
        if isinstance(output, GeneratorType):
            yield from output

    @inc_program_counter
    def _handle_controlled_qubit_rotation(
        self, subroutine_id: int, instr: ins.core.ControlledRotationInstruction
    ) -> Generator[Any, None, None]:
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address1 = self._get_register(app_id=app_id, register=instr.reg0)
        q_address2 = self._get_register(app_id=app_id, register=instr.reg1)
        assert q_address1 is not None
        assert q_address2 is not None
        angle = self._get_rotation_angle_from_operands(
            app_id=app_id, n=instr.angle_num.value, d=instr.angle_denom.value
        )
        self._logger.debug(
            f"Performing {instr} with angle {angle} "
            f"on the qubits at addresses {q_address1} and {q_address2}"
        )
        output = self._do_controlled_qubit_rotation(
            instr, subroutine_id, q_address1, q_address2, angle=angle
        )
        if isinstance(output, GeneratorType):
            yield from output

    def _get_rotation_angle_from_operands(self, app_id: int, n: int, d: int) -> float:
        return float(n * np.pi / 2 ** d)

    def _do_single_qubit_rotation(
        self,
        instr: ins.core.RotationInstruction,
        subroutine_id: int,
        address: int,
        angle: float,
    ) -> Optional[Generator[Any, None, None]]:
        """Perform a single-qubit rotation.

        This is a generator to allow simulators to yield at certain points during
        execution, e.g. to yield control to an asynchronous runtime.

        :param instr: NetQASM instruction to execute
        :param subroutine_id: ID of subroutine currently being executed
        :param address: virtual ID of qubit to act on
        :param angle: angle to rotate about
        :return: [description]
        """
        return None

    def _do_controlled_qubit_rotation(
        self,
        instr: ins.core.ControlledRotationInstruction,
        subroutine_id: int,
        address1: int,
        address2: int,
        angle: float,
    ) -> Optional[Generator[Any, None, None]]:
        """Perform a single-qubit controlled rotation.

        This is a generator to allow simulators to yield at certain points during
        execution, e.g. to yield control to an asynchronous runtime.

        :param instr: NetQASM instruction to execute
        :param subroutine_id: ID of subroutine currently being executed
        :param address1: virtual ID of control qubit
        :param address2: virtual ID of target qubit
        :param angle: angle to rotate about
        :return: [description]
        """
        return None

    @inc_program_counter
    def _handle_two_qubit_instr(
        self, subroutine_id: int, instr: ins.core.TwoQubitInstruction
    ) -> Generator[Any, None, None]:
        """Handle a two-qubit NetQASM instruction.

        Gets the virtual ID of the qubits and then calls `_do_two_qubit_instr`.

        This is a generator so that implementations of `_do_two_qubit_instr` can
        be generators themselves.
        """
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address1 = self._get_register(app_id=app_id, register=instr.reg0)
        q_address2 = self._get_register(app_id=app_id, register=instr.reg1)
        assert q_address1 is not None
        assert q_address2 is not None
        self._logger.debug(
            f"Performing {instr} on the qubits at addresses {q_address1} and {q_address2}"
        )
        output = self._do_two_qubit_instr(instr, subroutine_id, q_address1, q_address2)
        if isinstance(output, GeneratorType):
            yield from output

    def _do_two_qubit_instr(
        self,
        instr: ins.core.TwoQubitInstruction,
        subroutine_id: int,
        address1: int,
        address2: int,
    ) -> Optional[Generator[Any, None, None]]:
        """Perform a two-qubit gate.

        This is a generator to allow simulators to yield at certain points during
        execution, e.g. to yield control to an asynchronous runtime.

        :param instr: NetQASM instruction to execute
        :param subroutine_id: ID of subroutine currently being executed
        :param address1: virtual ID of first qubit
        :param address2: virtual ID of second qubit
        :return: [description]
        """
        return None

    @inc_program_counter
    def _instr_meas(
        self, subroutine_id: int, instr: ins.core.MeasInstruction
    ) -> Generator[Any, None, None]:
        """Handle a `meas` NetQASM instruction.

        Gets the virtual ID of the qubit and then calls `_do_meas`.

        This is a generator so that implementations of `do_meas` can
        be generators themselves.

        :return: measurement outcome (0 or 1)
        """
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address = self._get_register(app_id=app_id, register=instr.qreg)
        assert q_address is not None
        self._logger.debug(
            f"Measuring the qubit at address {q_address}, "
            f"placing the outcome in register {instr.creg}"
        )
        do_meas = self._do_meas(subroutine_id=subroutine_id, q_address=q_address)
        outcome: int
        if isinstance(do_meas, Generator):
            outcome = yield from do_meas  # type: ignore
        else:
            outcome = do_meas
        self._set_register(app_id=app_id, register=instr.creg, value=outcome)
        return outcome  # type: ignore

    def _do_meas(
        self, subroutine_id: int, q_address: int
    ) -> Union[int, Generator[int, None, None]]:
        """Perform a single-qubit measurement.

        This is a generator to allow simulators to yield at certain points during
        execution, e.g. to yield control to an asynchronous runtime.

        :param instr: NetQASM instruction to execute
        :param subroutine_id: ID of subroutine currently being executed
        :param address: virtual ID of qubit to act on
        :return: [description]
        """
        return 0

    @inc_program_counter
    def _instr_create_epr(
        self, subroutine_id: int, instr: ins.core.CreateEPRInstruction
    ) -> Generator[Any, None, None]:
        """Handle a `create_epr` NetQASM instruction.

        Gathers the relevant values from registers and then calls `_do_create_epr`.

        This is a generator so that implementations of `_do_create_epr` can
        be generators themselves.
        """
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        remote_node_id = self._get_register(
            app_id=app_id, register=instr.remote_node_id
        )
        epr_socket_id = self._get_register(app_id=app_id, register=instr.epr_socket_id)
        q_array_address = self._get_register(
            app_id=app_id, register=instr.qubit_addr_array
        )
        arg_array_address = self._get_register(app_id=app_id, register=instr.arg_array)
        ent_results_array_address = self._get_register(
            app_id=app_id, register=instr.ent_results_array
        )
        assert remote_node_id is not None
        assert epr_socket_id is not None
        # q_array_address can be None
        assert arg_array_address is not None
        assert ent_results_array_address is not None
        self._logger.debug(
            f"Creating EPR pair with remote node id {remote_node_id} and EPR socket ID {epr_socket_id}, "
            f"using qubit addresses stored in array with address {q_array_address}, "
            f"using arguments stored in array with address {arg_array_address}, "
            f"placing the entanglement information in array at address {ent_results_array_address}"
        )
        output = self._do_create_epr(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
            q_array_address=q_array_address,
            arg_array_address=arg_array_address,
            ent_results_array_address=ent_results_array_address,
        )
        if isinstance(output, GeneratorType):
            yield from output

    def _do_create_epr(
        self,
        subroutine_id: int,
        remote_node_id: int,
        epr_socket_id: int,
        q_array_address: Optional[int],
        arg_array_address: int,
        ent_results_array_address: int,
    ) -> Optional[Generator[Any, None, None]]:
        """Send a request to the Network Stack to create EPR pairs.

        This is a generator so that implementations of `_do_single_qubit_rotation` can
        be generators themselves.

        :param remote_node_id: ID of remote node
        :param epr_socket_id: ID of local EPR socket
        :param q_array_address: address of array containing virtual qubits IDs.
        These IDs are mapped to local halves of the generated pairs.
        :param arg_array_address: address of array containing request information
        :param ent_results_array_address: address of array that will hold generation
        information after EPR generation has completed
        """
        if self.network_stack is None:
            raise RuntimeError("SubroutineHandler has no network stack")
        create_request = self._get_create_request(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
            arg_array_address=arg_array_address,
        )
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        if create_request.type == RequestType.K:
            assert q_array_address is not None
            q_array = self._app_arrays[app_id][q_array_address, :]
            assert isinstance(q_array, list)
            num_qubits = len(q_array)
            assert num_qubits == create_request.number, "Not enough qubit addresses"
        self.network_stack.put(request=create_request)
        self._epr_create_requests[remote_node_id, create_request.purpose_id].append(
            EprCmdData(
                subroutine_id=subroutine_id,
                ent_results_array_address=ent_results_array_address,
                q_array_address=q_array_address,
                request=create_request,
                tot_pairs=create_request.number,
                pairs_left=create_request.number,
            )
        )
        return None

    def _get_create_request(
        self,
        subroutine_id: int,
        remote_node_id: int,
        epr_socket_id: int,
        arg_array_address: int,
    ) -> LinkLayerCreate:
        purpose_id = self._get_purpose_id(
            remote_node_id=remote_node_id, epr_socket_id=epr_socket_id
        )
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        array_args = self._app_arrays[app_id][arg_array_address, :]
        assert isinstance(array_args, list)

        # Not all values have to be defined (a default will be used).

        # assert all(arg is not None for arg in array_args)

        args = [remote_node_id, purpose_id] + array_args  # type: ignore

        # Use defaults if not specified
        expected_num_args = len(LinkLayerCreate._fields)
        if len(args) != expected_num_args:
            raise ValueError(
                f"Expected {expected_num_args} arguments, but got {len(args)}"
            )
        kwargs = {}
        for arg, field, default in zip(
            args, LinkLayerCreate._fields, LinkLayerCreate.__new__.__defaults__  # type: ignore
        ):
            if arg is None:
                kwargs[field] = default
            else:
                kwargs[field] = arg
        kwargs["type"] = RequestType(kwargs["type"])  # type: ignore

        return LinkLayerCreate(**kwargs)

    def _get_purpose_id(self, remote_node_id: int, epr_socket_id: int) -> int:
        # Should be subclassed
        # Note this is for now since we communicate directly to link layer
        if self._network_stack is None:
            raise RuntimeError("Exectioner has not network stack")
        return self._network_stack.get_purpose_id(
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
        )

    @inc_program_counter
    def _instr_recv_epr(
        self, subroutine_id: int, instr: ins.core.RecvEPRInstruction
    ) -> Generator[Any, None, None]:
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        remote_node_id = self._get_register(
            app_id=app_id, register=instr.remote_node_id
        )
        epr_socket_id = self._get_register(app_id=app_id, register=instr.epr_socket_id)
        q_array_address = self._get_register(
            app_id=app_id, register=instr.qubit_addr_array
        )
        ent_results_array_address = self._get_register(
            app_id=app_id, register=instr.ent_results_array
        )
        assert remote_node_id is not None
        assert epr_socket_id is not None
        # q_address can be None
        assert ent_results_array_address is not None
        self._logger.debug(
            f"Receiving EPR pair with remote node id {remote_node_id} "
            f"and EPR socket ID {epr_socket_id}, "
            f"using qubit addresses stored in array with address {q_array_address}, "
            f"placing the entanglement information in array at address {ent_results_array_address}"
        )
        output = self._do_recv_epr(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
            q_array_address=q_array_address,
            ent_results_array_address=ent_results_array_address,
        )
        if isinstance(output, GeneratorType):
            yield from output

    def _do_recv_epr(
        self,
        subroutine_id: int,
        remote_node_id: int,
        epr_socket_id: int,
        q_array_address: Optional[int],
        ent_results_array_address: int,
    ) -> Optional[Generator[Any, None, None]]:
        if self.network_stack is None:
            raise RuntimeError("SubroutineHandler has no network stack")
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        # Get number of pairs based on length of ent info array
        num_pairs = self._get_num_pairs_from_array(
            app_id=app_id,
            ent_results_array_address=ent_results_array_address,
        )
        purpose_id = self._get_purpose_id(
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
        )
        self._epr_recv_requests[remote_node_id, purpose_id].append(
            EprCmdData(
                subroutine_id=subroutine_id,
                ent_results_array_address=ent_results_array_address,
                q_array_address=q_array_address,
                request=None,
                tot_pairs=num_pairs,
                pairs_left=num_pairs,
            )
        )
        return None

    def _get_num_pairs_from_array(
        self, app_id: int, ent_results_array_address: int
    ) -> int:
        ent_info = self._app_arrays[app_id][ent_results_array_address, :]
        assert isinstance(ent_info, list)
        return int(len(ent_info) / OK_FIELDS)

    @inc_program_counter
    def _instr_wait_all(
        self, subroutine_id: int, instr: ins.core.WaitAllInstruction
    ) -> Generator[Any, None, None]:
        array_slice = instr.slice
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._logger.debug(
            f"Waiting for all entries in array slice {array_slice} to become defined"
        )
        address, index = self._expand_array_part(app_id=app_id, array_part=array_slice)
        while True:
            values = self._app_arrays[app_id][address, index]
            if not isinstance(values, list):
                raise RuntimeError(
                    f"Something went wrong: values should be a list but it is a {type(values)}"
                )
            if any(value is None for value in values):
                output = self._do_wait()
                if isinstance(output, GeneratorType):
                    yield from output
            else:
                break
        self._logger.debug(f"Finished waiting for array slice {array_slice}")

    @inc_program_counter
    def _instr_wait_any(
        self, subroutine_id: int, instr: ins.core.WaitAnyInstruction
    ) -> Generator[Any, None, None]:
        array_slice = instr.slice
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._logger.debug(
            f"Waiting for any entry in array slice {array_slice} to become defined"
        )
        while True:
            values = self._get_array_slice(app_id=app_id, array_slice=array_slice)
            if values is None:
                raise RuntimeError(f"array slice {array_slice} does not exist")
            if all(value is None for value in values):
                output = self._do_wait()
                if isinstance(output, GeneratorType):
                    yield from output
            else:
                break
        self._logger.debug(f"Finished waiting for array slice {array_slice}")

    @inc_program_counter
    def _instr_wait_single(
        self, subroutine_id: int, instr: ins.core.WaitSingleInstruction
    ) -> Generator[Any, None, None]:
        array_entry = instr.entry
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._logger.debug(f"Waiting for array entry {array_entry} to become defined")
        while True:
            value = self._get_array_entry(app_id=app_id, array_entry=array_entry)
            if value is None:
                output = self._do_wait()
                if isinstance(output, GeneratorType):
                    yield from output
            else:
                break
        self._logger.debug(f"Finished waiting for array entry {array_entry}")

    def _do_wait(self) -> Optional[Generator[Any, None, None]]:
        return None

    @inc_program_counter
    def _instr_qfree(
        self, subroutine_id: int, instr: ins.core.QFreeInstruction
    ) -> Generator[Any, None, None]:
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address = self._get_register(app_id=app_id, register=instr.reg)
        assert q_address is not None
        self._logger.debug(f"Freeing qubit at virtual address {q_address}")
        yield from self._free_physical_qubit(subroutine_id, q_address)

    @inc_program_counter
    def _instr_ret_reg(
        self, subroutine_id: int, instr: ins.core.RetRegInstruction
    ) -> None:
        register = instr.reg
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        value = self._get_register(app_id=app_id, register=register)
        if value is None:
            raise RuntimeError(
                f"Trying to return register {register} but it does not have value"
            )
        self._update_shared_memory(app_id=app_id, entry=register, value=value)

    @inc_program_counter
    def _instr_ret_arr(
        self, subroutine_id: int, instr: ins.core.RetArrInstruction
    ) -> None:
        address = instr.address
        app_id = self._get_app_id(subroutine_id=subroutine_id)

        array = self._get_array(app_id=app_id, address=address)

        # Not all values need to be defined.

        # if not all(elt is not None for elt in array):
        #     raise RuntimeError(
        #         f"Trying to return array {array} but not all values are defined yet"
        #     )

        self._update_shared_memory(
            app_id=app_id, entry=address, value=array  # type: ignore
        )

    def _update_shared_memory(
        self,
        app_id: int,
        entry: Union[operand.Register, Address, ArrayEntry, ArraySlice],
        value: Union[int, List[int]],
    ):
        shared_memory = self._shared_memories[app_id]
        if isinstance(entry, operand.Register):
            assert isinstance(value, int)
            self._logger.debug(
                f"Updating host about register {entry} with value {value}"
            )
            shared_memory.set_register(entry, value)
        elif isinstance(entry, ArrayEntry) or isinstance(entry, ArraySlice):
            self._logger.debug(
                f"Updating host about array entry {entry} with value {value}"
            )
            address, index = self._expand_array_part(app_id=app_id, array_part=entry)
            shared_memory.set_array_part(address=address, index=index, value=value)  # type: ignore
        elif isinstance(entry, Address):
            self._logger.debug(f"Updating host about array {entry} with value {value}")
            address = entry.address
            shared_memory.init_new_array(address=address, new_array=value)  # type: ignore
        else:
            raise TypeError(
                f"Cannot update shared memory with entry specified as {entry}"
            )

    def _get_unit_module(self, subroutine_id: int) -> T_UnitModule:
        app_id = self._get_app_id(subroutine_id)
        unit_module = self._qubit_unit_modules.get(app_id)
        if unit_module is None:
            raise RuntimeError(
                f"Application with app ID {app_id} has not allocated qubit unit module"
            )
        return unit_module

    def _get_position_in_unit_module(self, app_id: int, address: int) -> int:
        unit_module = self._qubit_unit_modules.get(app_id)
        if unit_module is None:
            raise RuntimeError(
                f"Application with app ID {app_id} has not allocated qubit unit module"
            )
        if address >= len(unit_module):
            raise IndexError(
                f"The address {address} is not within the allocated unit module "
                f"of size {len(unit_module)}"
            )
        position = unit_module[address]
        if position is None:
            raise NotAllocatedError(
                f"The qubit with address {address} was not allocated "
                f"for app ID {app_id} for node {self._name}"
            )
        return position

    def _get_array(self, app_id: int, address: Address) -> List[Optional[int]]:
        return self._app_arrays[app_id]._get_array(address.address)

    def _get_array_entry(self, app_id: int, array_entry: ArrayEntry) -> Optional[int]:
        address, index = self._expand_array_part(app_id=app_id, array_part=array_entry)
        result = self._app_arrays[app_id][address, index]
        assert (result is None) or isinstance(result, int)
        return result

    def _set_array_entry(
        self, app_id: int, array_entry: ArrayEntry, value: Optional[int]
    ) -> None:
        address, index = self._expand_array_part(app_id=app_id, array_part=array_entry)
        self._app_arrays[app_id][address, index] = value

    def _get_array_slice(
        self, app_id: int, array_slice: ArraySlice
    ) -> Optional[List[Optional[int]]]:
        address, index = self._expand_array_part(app_id=app_id, array_part=array_slice)
        result = self._app_arrays[app_id][address, index]
        assert (result is None) or isinstance(result, list)
        return result

    def _expand_array_part(
        self, app_id: int, array_part: Union[ArrayEntry, ArraySlice]
    ) -> Tuple[int, Union[int, slice]]:
        address: int = array_part.address.address
        index: Union[int, slice]
        if isinstance(array_part, ArrayEntry):
            if isinstance(array_part.index, int):
                index = array_part.index
            else:
                index_from_reg = self._get_register(
                    app_id=app_id, register=array_part.index
                )
                if index_from_reg is None:
                    raise RuntimeError(
                        f"Trying to use register {array_part.index} to index an array but its value is None"
                    )
                index = index_from_reg
        elif isinstance(array_part, ArraySlice):
            startstop: List[int] = []
            for raw_s in [array_part.start, array_part.stop]:
                if isinstance(raw_s, int):
                    startstop.append(raw_s)
                elif isinstance(raw_s, operand.Register):
                    s = self._get_register(app_id=app_id, register=raw_s)
                    if s is None:
                        raise RuntimeError(
                            f"Trying to use register {raw_s} to index an array but its value is None"
                        )
                    startstop.append(s)
                else:
                    raise RuntimeError(
                        f"Something went wrong: raw_s should be int or Register but is {type(raw_s)}"
                    )
            index = slice(*startstop)
        else:
            raise RuntimeError(
                f"Something went wrong: array_part is a {type(array_part)}"
            )
        return address, index

    def allocate_new_qubit_unit_module(self, app_id: int, num_qubits: int) -> None:
        unit_module = self._get_new_qubit_unit_module(num_qubits)
        self._qubit_unit_modules[app_id] = unit_module

    def _get_new_qubit_unit_module(self, num_qubits: int) -> T_UnitModule:
        return [None] * num_qubits

    def _has_virtual_address(self, app_id: int, virtual_address: int) -> bool:
        unit_module = self._qubit_unit_modules.get(app_id)
        if unit_module is None:
            return False
        if virtual_address < 0 or virtual_address >= len(unit_module):
            return False
        return unit_module[virtual_address] is not None

    def _allocate_physical_qubit(
        self,
        subroutine_id: int,
        virtual_address: int,
        physical_address: Optional[int] = None,
    ) -> int:
        """[summary]

        :param subroutine_id: [description]
        :param virtual_address: [description]
        :param physical_address: [description], defaults to None
        :raises ValueError: [description]
        :raises RuntimeError: [description]
        :return: physical qubit ID
        """
        unit_module = self._get_unit_module(subroutine_id)
        if virtual_address >= len(unit_module):
            app_id = self._subroutines[subroutine_id].app_id
            raise ValueError(
                f"Virtual address {virtual_address} is outside the unit module (app ID {app_id}) "
                f"which has length {len(unit_module)}"
            )
        if unit_module[virtual_address] is None:
            if physical_address is None:
                physical_address = self._get_unused_physical_qubit()
                self._used_physical_qubit_addresses.add(physical_address)
            unit_module[virtual_address] = physical_address
            self._reserve_physical_qubit(physical_address)
            return physical_address
        else:
            app_id = self._subroutines[subroutine_id].app_id
            raise RuntimeError(
                f"QubitAddress at address {virtual_address} "
                f"for application {app_id} is already allocated"
            )

    def _free_physical_qubit(
        self, subroutine_id: int, address: int
    ) -> Generator[Any, None, None]:
        unit_module = self._get_unit_module(subroutine_id)
        if unit_module[address] is None:
            app_id = self._subroutines[subroutine_id].app_id
            raise RuntimeError(
                f"QubitAddress at address {address} for application {app_id} is not allocated "
                "and cannot be freed"
            )
        else:
            physical_address = unit_module[address]
            assert physical_address is not None
            self._logger.debug(f"Freeing qubit at physical address {physical_address}")
            unit_module[address] = None
            self._used_physical_qubit_addresses.remove(physical_address)
            output = self._clear_phys_qubit_in_memory(physical_address)
            if isinstance(output, GeneratorType):
                yield from output

    def _reserve_physical_qubit(
        self, physical_address: int
    ) -> Generator[Any, None, None]:
        """To be subclassed for different quantum processors (e.g. netsquid)"""
        yield None

    def _clear_phys_qubit_in_memory(
        self, physical_address: int
    ) -> Generator[Any, None, None]:
        """To be subclassed for different quantum processors (e.g. netsquid)"""
        yield None

    def _get_unused_physical_qubit(self) -> int:
        # Assuming that the topology of the unit module is a complete graph
        # is does not matter which unused physical qubit we choose for now
        for physical_address in count(0):
            if physical_address not in self._used_physical_qubit_addresses:
                self._used_physical_qubit_addresses.add(physical_address)
                return physical_address
        raise RuntimeError("should never get here")

    def _get_app_id(self, subroutine_id: int) -> int:
        """Returns the app ID for the given subroutine"""
        subroutine = self._subroutines.get(subroutine_id)
        if subroutine is None:
            raise ValueError(f"Unknown subroutine with ID {subroutine_id}")
        return subroutine.app_id

    def _handle_epr_response(self, response: T_LinkLayerResponse) -> None:

        if (
            isinstance(response, qlink_1_0.ResCreateAndKeep)
            or isinstance(response, qlink_1_0.ResMeasureDirectly)
            or isinstance(response, qlink_1_0.ResError)
        ):
            # Convert from qlink-layer 1.0
            response = response_from_qlink_1_0(response)

        self._pending_epr_responses.append(response)
        self._handle_pending_epr_responses()

    def _handle_pending_epr_responses(self) -> None:
        # NOTE this will probably be handled differently in an actual implementation
        # but is done in a simple way for now to allow for simulation
        if len(self._pending_epr_responses) == 0:
            return

        # Try to handle one of the pending EPR responses
        handled = False
        for i, response in enumerate(self._pending_epr_responses):

            if response.type == ReturnType.ERR:
                self._handle_epr_err_response(response)  # type: ignore
            else:
                self._logger.debug(
                    f"Try to handle EPR OK ({response.type}) response from network stack"
                )
                info = self._extract_epr_info(response=response)  # type: ignore
                if info is not None:
                    epr_cmd_data, pair_index, is_creator, request_key = info
                    handled = self._epr_response_handlers[response.type](
                        epr_cmd_data=epr_cmd_data,
                        response=response,
                        pair_index=pair_index,
                    )
                if handled:
                    epr_cmd_data.pairs_left -= 1

                    self._handle_last_epr_pair(
                        epr_cmd_data=epr_cmd_data,
                        is_creator=is_creator,
                        request_key=request_key,
                    )

                    self._store_ent_info(
                        epr_cmd_data=epr_cmd_data,
                        response=response,  # type: ignore
                        pair_index=pair_index,
                    )
                    self._pending_epr_responses.pop(i)
                    break
        if not handled:
            self._wait_to_handle_epr_responses()
        else:
            self._handle_pending_epr_responses()

    def _wait_to_handle_epr_responses(self) -> None:
        # This can be subclassed to sleep a little before handling again
        self._handle_pending_epr_responses()

    def _handle_epr_err_response(self, response: LinkLayerErr) -> None:
        raise RuntimeError(
            f"Got the following error from the network stack: {response}"
        )

    def _extract_epr_info(
        self, response: T_LinkLayerResponseOK
    ) -> Optional[Tuple[EprCmdData, int, bool, T_RequestKey]]:
        creator_node_id: int = get_creator_node_id(self.node_id, response)  # type: ignore

        # Retreive the data for this request (depending on if we are creator or receiver
        if creator_node_id == self.node_id:
            is_creator = True
            requests = self._epr_create_requests
        else:
            is_creator = False
            requests = self._epr_recv_requests

        purpose_id = response.purpose_id
        remote_node_id = response.remote_node_id
        request_key = remote_node_id, purpose_id
        if len(requests[request_key]) == 0:
            self._logger.debug(
                f"Since there is yet not recv request for remote node ID {remote_node_id} and "
                f"purpose ID {purpose_id}, "
                "handling of epr will wait and try again."
            )
            return None
        epr_cmd_data = requests[request_key][0]

        pair_index = epr_cmd_data.tot_pairs - epr_cmd_data.pairs_left

        return epr_cmd_data, pair_index, is_creator, request_key

    def _handle_last_epr_pair(
        self, epr_cmd_data: EprCmdData, is_creator: bool, request_key: T_RequestKey
    ) -> None:
        # Check if this was the last pair
        if epr_cmd_data.pairs_left == 0:
            if is_creator:
                self._epr_create_requests[request_key].pop(0)
            else:
                self._epr_recv_requests[request_key].pop(0)

    def _store_ent_info(
        self, epr_cmd_data: EprCmdData, response: T_LinkLayerResponseOK, pair_index: int
    ) -> None:
        # Store the entanglement information
        ent_info = [
            entry.value if isinstance(entry, Enum) else entry for entry in response
        ]
        ent_results_array_address = epr_cmd_data.ent_results_array_address
        self._logger.debug(
            f"Storing entanglement information for pair {pair_index} "
            f"in array at address {ent_results_array_address}"
        )
        # Start and stop of slice
        arr_start = pair_index * OK_FIELDS
        arr_stop = (pair_index + 1) * OK_FIELDS
        subroutine_id = epr_cmd_data.subroutine_id
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        if app_id not in self._app_arrays:
            raise KeyError("App ID {app_id} does not have any arrays")
        self._app_arrays[app_id][
            ent_results_array_address, arr_start:arr_stop
        ] = ent_info

    def _handle_epr_ok_k_response(
        self, epr_cmd_data: EprCmdData, response: LinkLayerOKTypeK, pair_index: int
    ) -> bool:
        # Extract qubit addresses
        subroutine_id = epr_cmd_data.subroutine_id
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        virtual_address = self._get_virtual_address_from_epr_data(
            epr_cmd_data, pair_index, app_id
        )

        # If the virtual address is currently in use, we should wait
        if self._has_virtual_address(app_id=app_id, virtual_address=virtual_address):
            self._logger.debug(
                f"Since virtual address {virtual_address} is in use, "
                "handling of epr will wait and try again."
            )
            return False

        # Update qubit mapping
        physical_address = response.logical_qubit_id
        self._logger.debug(
            f"Virtual qubit address {virtual_address} will now be mapped to "
            f"physical address {physical_address}"
        )
        self._used_physical_qubit_addresses.add(physical_address)
        self._allocate_physical_qubit(
            subroutine_id=subroutine_id,
            virtual_address=virtual_address,
            physical_address=physical_address,
        )

        return True

    def _get_virtual_address_from_epr_data(
        self, epr_cmd_data: EprCmdData, pair_index: int, app_id: int
    ) -> int:
        q_array_address = epr_cmd_data.q_array_address
        array_entry = parse_address(f"@{q_array_address}[{pair_index}]")
        assert isinstance(array_entry, ArrayEntry)
        virtual_address = self._get_array_entry(app_id=app_id, array_entry=array_entry)
        if virtual_address is None:
            raise RuntimeError("virtual address is None")
        return virtual_address

    def _handle_epr_ok_m_response(
        self, epr_cmd_data: EprCmdData, response: LinkLayerOKTypeM, pair_index: int
    ) -> bool:
        # M request are always handled
        return True

    def _handle_epr_ok_r_response(self, response: LinkLayerOKTypeR) -> bool:
        raise NotImplementedError

    def _get_qubit(self, app_id: int, virtual_address: int) -> Any:
        raise NotImplementedError

    def _get_qubit_state(self, app_id: int, virtual_address: int) -> Any:
        raise NotImplementedError

    def _get_positions(self, subroutine_id: int, addresses: List[int]) -> List[int]:
        return [
            self._get_position(subroutine_id=subroutine_id, address=address)
            for address in addresses
        ]

    def _get_position(
        self,
        subroutine_id: Optional[int] = None,
        address: int = 0,
        app_id: Optional[int] = None,
    ) -> int:
        if app_id is None:
            if subroutine_id is None:
                raise ValueError("subroutine_id and app_id cannot both be None")
            app_id = self._get_app_id(subroutine_id=subroutine_id)
        return self._get_position_in_unit_module(app_id=app_id, address=address)
