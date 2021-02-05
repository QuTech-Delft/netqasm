"""TODO write about connections"""

import os
import abc
import math
import pickle
from enum import Enum
from itertools import count
from contextlib import contextmanager
from typing import List, Optional, Dict, Type

from qlink_interface import (
    EPRType,
    RandomBasis,
    LinkLayerCreate,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerOKTypeR,
)
from netqasm import NETQASM_VERSION
from netqasm.logging.glob import get_netqasm_logger
from netqasm.lang.parsing.text import assemble_subroutine, parse_register, get_current_registers, parse_address
from netqasm.lang.instr.instr_enum import Instruction, flip_branch_instr
from netqasm.sdk.shared_memory import get_shared_memory
from netqasm.sdk.qubit import Qubit, _FutureQubit
from netqasm.sdk.futures import Future, RegFuture, Array
from netqasm.sdk.toolbox import get_angle_spec_from_float
from netqasm.sdk.progress_bar import ProgressBar
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.util.log import LineTracker
from netqasm.backend.network_stack import OK_FIELDS
from netqasm.lang.encoding import RegisterName, REG_INDEX_BITS
from netqasm.lang.subroutine import (
    PreSubroutine,
    Subroutine,
    Command,
    Register,
    Address,
    ArrayEntry,
    ArraySlice,
    Label,
    BranchLabel,
    Symbols,
)
from netqasm.backend.messages import (
    Signal,
    InitNewAppMessage,
    StopAppMessage,
    OpenEPRSocketMessage,
    SubroutineMessage,
    SignalMessage,
)
from netqasm.sdk.config import LogConfig
from netqasm.sdk.network import NetworkInfo


# NOTE this is needed to be able to instanciate tuples the same way as namedtuples
class _Tuple(tuple):
    @classmethod
    def __new__(cls, *args, **kwargs):
        return tuple.__new__(cls, args[1:])


class BaseNetQASMConnection(abc.ABC):

    # Used app IDs
    _app_ids: Dict[str, List[int]] = {}

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
        app_name,
        node_name=None,
        app_id=None,
        max_qubits=5,
        log_config=None,
        epr_sockets=None,
        compiler=None,
        return_arrays=True,
        _init_app=True,
        _setup_epr_sockets=True,
    ):
        self._app_name = app_name

        # Set an app ID
        self._app_id = self._get_new_app_id(app_id)

        if node_name is None:
            node_name = self.network_info.get_node_name_for_app(app_name)
        self._node_name = node_name

        if node_name not in self._app_names:
            self._app_names[node_name] = {}
        self._app_names[node_name][self._app_id] = app_name

        # All qubits active for this connection
        self.active_qubits = []

        self._used_array_addresses = []

        self._used_meas_registers = []

        self._pending_commands = []

        self._max_qubits = max_qubits

        self._shared_memory = get_shared_memory(self.node_name, key=self._app_id)

        # Registers for looping etc.
        # These are registers that are for example currently hold data and should
        # not be used for something else.
        # For example a register used for looping.
        self._active_registers = set()

        # Arrays to return
        self._arrays_to_return = []

        # If False, don't return arrays even if they are used in a subroutine
        self._return_arrays = return_arrays

        # Registers to return
        self._registers_to_return = []

        # Storing commands before an conditional statement
        self._pre_context_commands = {}

        # Can be set to false for e.g. debugging, not exposed to user atm
        self._clear_app_on_exit = True
        self._stop_backend_on_exit = True

        if log_config is None:
            log_config = LogConfig()

        self._line_tracker = LineTracker(log_config=log_config)
        self._track_lines = log_config.track_lines

        # Should subroutines commited be saved for logging/debugging
        self._log_subroutines_dir = log_config.log_subroutines_dir
        # Commited subroutines saved for logging/debugging
        self._commited_subroutines: List[Subroutine] = []

        # What compiler (if any) to be used
        self._compiler = compiler

        self._logger = get_netqasm_logger(f"{self.__class__.__name__}({self.app_name})")

        if _init_app:
            self._init_new_app(max_qubits=max_qubits)

        if _setup_epr_sockets:
            # Setup epr sockets
            self._setup_epr_sockets(epr_sockets=epr_sockets)

    @property
    def app_name(self):
        """Get the application name"""
        return self._app_name

    @property
    def node_name(self):
        """Get the node name"""
        return self._node_name

    @property
    def app_id(self):
        """Get the application ID"""
        return self._app_id

    @abc.abstractmethod
    def _get_network_info(self) -> Type[NetworkInfo]:
        raise NotImplementedError

    @property
    def network_info(self) -> Type[NetworkInfo]:
        return self._get_network_info()

    @classmethod
    def get_app_ids(cls):
        return cls._app_ids

    @classmethod
    def get_app_names(cls):
        return cls._app_names

    def __str__(self):
        return f"NetQASM connection for app '{self.app_name}' with node '{self.node_name}'"

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

    def _get_new_app_id(self, app_id):
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
        else:
            if app_id in self._app_ids[name]:
                raise ValueError("app_id={} is already in use".format(app_id))
            self._app_ids[name].append(app_id)
            return app_id

    def _pop_app_id(self):
        """
        Removes the used app ID from the list.
        """
        try:
            self._app_ids[self.app_name].remove(self.app_id)
        except ValueError:
            pass  # Already removed

    def clear(self):
        self._pop_app_id()

    def close(self, clear_app=True, stop_backend=True):
        """Handle exiting of context."""
        # Flush all pending commands
        self.flush()

        self._pop_app_id()

        self._signal_stop(clear_app=clear_app, stop_backend=stop_backend)
        self._inactivate_qubits()

        if self._log_subroutines_dir is not None:
            self._save_log_subroutines()

    def _commit_message(self, msg, block=True, callback=None):
        """Commit a message to the backend/qnodeos"""
        self._logger.debug(f"Committing message {msg}")
        self._commit_serialized_message(raw_msg=bytes(msg), block=block, callback=callback)

    @abc.abstractmethod
    def _commit_serialized_message(self, raw_msg, block=True, callback=None):
        """Commit a message to the backend/qnodeos"""
        # Should be subclassed
        pass

    def _inactivate_qubits(self):
        while len(self.active_qubits) > 0:
            q = self.active_qubits.pop()
            q.active = False

    def _signal_stop(self, clear_app=True, stop_backend=True):
        if clear_app:
            self._commit_message(msg=StopAppMessage(app_id=self._app_id))

        if stop_backend:
            self._commit_message(msg=SignalMessage(signal=Signal.STOP), block=False)

    def _save_log_subroutines(self):
        filename = f'subroutines_{self.app_name}.pkl'
        filepath = os.path.join(self._log_subroutines_dir, filename)
        with open(filepath, 'wb') as f:
            pickle.dump(self._commited_subroutines, f)

    @property
    def shared_memory(self):
        return self._shared_memory

    def new_qubit_id(self):
        return self._get_new_qubit_address()

    def _init_new_app(self, max_qubits):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        self._commit_message(msg=InitNewAppMessage(
            app_id=self._app_id,
            max_qubits=max_qubits,
        ))

    def _setup_epr_sockets(self, epr_sockets):
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

    def _setup_epr_socket(self, epr_socket_id, remote_node_id, remote_epr_socket_id, min_fidelity):
        """Sets up a new epr socket"""
        self._commit_message(msg=OpenEPRSocketMessage(
            app_id=self._app_id,
            epr_socket_id=epr_socket_id,
            remote_node_id=remote_node_id,
            remote_epr_socket_id=remote_epr_socket_id,
            min_fidelity=min_fidelity,
        ))

    def new_array(self, length=1, init_values=None):
        address = self._get_new_array_address()
        lineno = self._line_tracker.get_line()
        array = Array(
            connection=self,
            length=length,
            address=address,
            init_values=init_values,
            lineno=lineno,
        )
        self._arrays_to_return.append(array)
        return array

    def add_pending_commands(self, commands):
        calling_lineno = self._line_tracker.get_line()
        for command in commands:
            if command.lineno is None:
                command.lineno = calling_lineno
            self.add_pending_command(command)

    def add_pending_command(self, command):
        assert isinstance(command, Command) or isinstance(command, BranchLabel)
        if command.lineno is None:
            command.lineno = self._line_tracker.get_line()
        self._pending_commands.append(command)

    def flush(self, block=True, callback=None):
        subroutine = self._pop_pending_subroutine()
        if subroutine is None:
            return

        self._commit_subroutine(
            presubroutine=subroutine,
            block=block,
            callback=callback,
        )

    def _commit_subroutine(self, presubroutine: PreSubroutine, block=True, callback=None):
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

        self._reset()

    def _pop_pending_subroutine(self) -> Optional[PreSubroutine]:
        # Add commands for initialising and returning arrays
        self._add_array_commands()
        self._add_ret_reg_commands()
        subroutine = None
        if len(self._pending_commands) > 0:
            commands = self._pop_pending_commands()
            subroutine = self._subroutine_from_commands(commands)
        return subroutine

    def _add_ret_reg_commands(self):
        ret_reg_instrs = []
        for reg in self._registers_to_return:
            ret_reg_instrs.append(Command(
                instruction=Instruction.RET_REG,
                operands=[reg]
            ))
        self.add_pending_commands(commands=ret_reg_instrs)

    def _add_array_commands(self):
        current_commands = self._pop_pending_commands()
        array_commands = self._get_array_commands()
        init_arrays, return_arrays = array_commands
        commands = init_arrays + current_commands + return_arrays
        self.add_pending_commands(commands=commands)

    def _get_array_commands(self):
        init_arrays = []
        return_arrays = []
        for array in self._arrays_to_return:
            # Command for initialising the array
            init_arrays.append(Command(
                instruction=Instruction.ARRAY,
                operands=[
                    len(array),
                    Address(array.address),
                ],
                lineno=array.lineno,
            ))
            # Populate the array if needed
            if array._init_values is not None:
                for i, value in enumerate(array._init_values):
                    if value is None:
                        continue
                    init_arrays.append(Command(
                        instruction=Instruction.STORE,
                        operands=[
                            value,
                            ArrayEntry(Address(array.address), i),
                        ],
                        lineno=array.lineno,
                    ))
            # Command for returning the array by the end of the subroutine
            if self._return_arrays:
                return_arrays.append(Command(
                    instruction=Instruction.RET_ARR,
                    operands=[
                        Address(array.address),
                    ],
                    lineno=array.lineno,
                ))
        return init_arrays, return_arrays

    def _subroutine_from_commands(self, commands) -> PreSubroutine:
        # Build sub-routine
        metadata = self._get_metadata()
        return PreSubroutine(**metadata, commands=commands)  # type: ignore

    def _get_metadata(self):
        return {
            "netqasm_version": NETQASM_VERSION,
            "app_id": self._app_id,
        }

    def _pop_pending_commands(self):
        commands = self._pending_commands
        self._pending_commands = []
        return commands

    def _pre_process_subroutine(self, pre_subroutine: PreSubroutine) -> Subroutine:
        """Parses and assembles the subroutine.

        Can be subclassed and overried for more elaborate compiling.
        """
        subroutine: Subroutine = assemble_subroutine(pre_subroutine)
        if self._compiler is not None:
            subroutine = self._compiler(subroutine=subroutine).compile()
        if self._track_lines:
            self._log_subroutine(subroutine=subroutine)
        return subroutine

    def _log_subroutine(self, subroutine):
        self._commited_subroutines.append(subroutine)

    def block(self):
        """Block until flushed subroutines finish"""
        raise NotImplementedError

    def add_single_qubit_rotation_commands(self, instruction, virtual_qubit_id, n=0, d=0, angle=None):
        if angle is not None:
            nds = get_angle_spec_from_float(angle=angle)
            for n, d in nds:
                self.add_single_qubit_rotation_commands(
                    instruction=instruction,
                    virtual_qubit_id=virtual_qubit_id,
                    n=n,
                    d=d,
                )
            return
        if not (isinstance(n, int) and isinstance(d, int) and n >= 0 and d >= 0):
            raise ValueError(f'{n} * pi / 2 ^ {d} is not a valid angle specification')
        register, set_commands = self._get_set_qubit_reg_commands(virtual_qubit_id)
        rot_command = Command(
            instruction=instruction,
            operands=[register, n, d],
        )
        commands = set_commands + [rot_command]
        self.add_pending_commands(commands)

    def add_single_qubit_commands(self, instr, qubit_id):
        register, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        # Construct the qubit command
        qubit_command = Command(
            instruction=instr,
            operands=[register],
        )
        commands = set_commands + [qubit_command]
        self.add_pending_commands(commands)

    def _get_set_qubit_reg_commands(self, q_address, reg_index=0):
        # Set the register with the qubit address
        register = Register(RegisterName.Q, reg_index)
        if isinstance(q_address, Future):
            set_reg_cmds = q_address._get_load_commands(register)
        elif isinstance(q_address, int):
            set_reg_cmds = [Command(
                instruction=Instruction.SET,
                operands=[
                    register,
                    q_address,
                ],
            )]
        else:
            raise NotImplementedError("Setting qubit reg for other types not yet implemented")
        return register, set_reg_cmds

    def add_two_qubit_commands(self, instr, control_qubit_id, target_qubit_id):
        register1, set_commands1 = self._get_set_qubit_reg_commands(control_qubit_id, reg_index=0)
        register2, set_commands2 = self._get_set_qubit_reg_commands(target_qubit_id, reg_index=1)
        qubit_command = Command(
            instruction=instr,
            operands=[register1, register2],
        )
        commands = set_commands1 + set_commands2 + [qubit_command]
        self.add_pending_commands(commands=commands)

    def _add_move_qubit_commands(self, source, target):
        # Moves a qubit from one position to another (assumes that target is free)
        assert target not in [q.qubit_id for q in self.active_qubits]
        self.add_new_qubit_commands(target)
        self.add_two_qubit_commands(Instruction.MOV, source, target)
        self.add_qfree_commands(source)

    def _free_up_qubit(self, virtual_address):
        if self._compiler == NVSubroutineCompiler:
            for q in self.active_qubits:
                # Find a free qubit
                new_virtual_address = self._get_new_qubit_address()
                if q.qubit_id == virtual_address:
                    # Virtual address is already used. Move it to the new virtual address.
                    # NOTE: this assumes that the new virtual address is *not* currently used.
                    self._add_move_qubit_commands(source=virtual_address, target=new_virtual_address)
                    # From now on, the original qubit should be referred to with the new virtual address.
                    q.qubit_id = new_virtual_address

    def add_measure_commands(self, qubit_id, future, inplace):
        if self._compiler == NVSubroutineCompiler:
            # If compiling for NV, only virtual ID 0 can be used to measure a qubit.
            # So, if this qubit is already in use, we need to move it away first.
            if qubit_id != 0:
                self._free_up_qubit(virtual_address=0)
        outcome_reg = self._get_new_meas_outcome_reg()
        qubit_reg, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        meas_command = Command(
            instruction=Instruction.MEAS,
            operands=[qubit_reg, outcome_reg],
        )
        if not inplace:
            free_commands = [Command(
                instruction=Instruction.QFREE,
                operands=[qubit_reg],
            )]
        else:
            free_commands = []
        if future is not None:
            if isinstance(future, Future):
                outcome_commands = future._get_store_commands(outcome_reg)
            elif isinstance(future, RegFuture):
                future.reg = outcome_reg
                self._registers_to_return.append(outcome_reg)
                outcome_commands = []
            else:
                outcome_commands = []
        commands = set_commands + [meas_command] + free_commands + outcome_commands
        self.add_pending_commands(commands)

    def _get_new_meas_outcome_reg(self):
        # Find the next unused M-register.
        for i in range(16):
            if i not in self._used_meas_registers:
                self._used_meas_registers.append(i)
                return Register(RegisterName.M, i)

    def add_new_qubit_commands(self, qubit_id):
        qubit_reg, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        qalloc_command = Command(
            instruction=Instruction.QALLOC,
            operands=[qubit_reg],
        )
        init_command = Command(
            instruction=Instruction.INIT,
            operands=[qubit_reg],
        )
        commands = set_commands + [qalloc_command, init_command]
        self.add_pending_commands(commands)

    def add_init_qubit_commands(self, qubit_id):
        qubit_reg, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        init_command = Command(
            instruction=Instruction.INIT,
            operands=[qubit_reg],
        )
        commands = set_commands + [init_command]
        self.add_pending_commands(commands)

    def add_qfree_commands(self, qubit_id):
        qubit_reg, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        qfree_command = Command(
            instruction=Instruction.QFREE,
            operands=[qubit_reg],
        )
        commands = set_commands + [qfree_command]
        self.add_pending_commands(commands)

    def _add_epr_commands(
        self,
        instruction,
        virtual_qubit_ids,
        remote_node_id,
        epr_socket_id,
        number,
        ent_info_array,
        wait_all,
        tp,
        random_basis_local=None,
        random_basis_remote=None,
        **kwargs,
    ):
        # qubit addresses
        if tp == EPRType.K:
            qubit_ids_array = self.new_array(init_values=virtual_qubit_ids)
            qubit_ids_array_address = qubit_ids_array.address
        else:
            qubit_ids_array = None
            # NOTE since this argument won't be used just set it to some
            # constant register for now
            qubit_ids_array_address = Register(RegisterName.C, 0)

        if instruction == Instruction.CREATE_EPR:
            # request arguments
            # TODO add other args
            create_kwargs = {}
            create_kwargs['type'] = tp
            create_kwargs['number'] = number
            # TODO currently this give 50 / 50 since with the current link layer
            # This should change and not be hardcoded here
            if random_basis_local is not None:
                # NOTE Currently there is not value one can set to specify
                # a uniform distribution for three bases. This needs to be changed
                # in the underlying link layer/network stack
                assert random_basis_local in [RandomBasis.XZ, RandomBasis.CHSH], (
                    "Can only random measure in one of two bases for now")
                create_kwargs['random_basis_local'] = random_basis_local
                create_kwargs['probability_dist_local1'] = 128
            if random_basis_remote is not None:
                assert random_basis_remote in [RandomBasis.XZ, RandomBasis.CHSH], (
                    "Can only random measure in one of two bases for now")
                create_kwargs['random_basis_remote'] = random_basis_remote
                create_kwargs['probability_dist_remote1'] = 128

            create_args = []
            # NOTE we don't include the two first args since these are remote_node_id
            # and epr_socket_id which come as registers
            for field in LinkLayerCreate._fields[2:]:
                arg = create_kwargs.get(field)
                # If Enum, use its value
                if isinstance(arg, Enum):
                    arg = arg.value
                create_args.append(arg)
            # TODO don't create a new array if already created from previous command
            create_args_array = self.new_array(init_values=create_args)
            epr_cmd_operands = [
                qubit_ids_array_address,
                create_args_array.address,
                ent_info_array.address,
            ]
        elif instruction == Instruction.RECV_EPR:
            epr_cmd_operands = [
                qubit_ids_array_address,
                ent_info_array.address,
            ]
        else:
            raise ValueError(f"Not an epr instruction {instruction}")

        # epr command
        epr_cmd = Command(
            instruction=instruction,
            args=[remote_node_id, epr_socket_id],
            operands=epr_cmd_operands,
        )

        # wait
        if wait_all:
            wait_cmds = [Command(
                instruction=Instruction.WAIT_ALL,
                operands=[ArraySlice(ent_info_array.address, start=0, stop=len(ent_info_array))],
            )]
        else:
            wait_cmds = []

        commands = [epr_cmd] + wait_cmds
        self.add_pending_commands(commands)

        return qubit_ids_array

    def _add_post_commands(self, qubit_ids, number, ent_info_array, tp, post_routine=None):
        if post_routine is None:
            return []

        loop_register = self._get_inactive_register()

        def post_loop(conn):
            # Wait for each pair individually
            pair = loop_register
            conn._add_wait_for_ent_info_cmd(
                ent_info_array=ent_info_array,
                pair=pair,
            )
            if tp == EPRType.K:
                q_id = qubit_ids.get_future_index(pair)
                q = _FutureQubit(conn=conn, future_id=q_id)
                post_routine(self, q, pair)
            elif tp == EPRType.M:
                slc = slice(pair * OK_FIELDS, (pair + 1) * OK_FIELDS)
                ent_info_slice = ent_info_array.get_future_slice(slc)
                post_routine(self, ent_info_slice, pair)
            else:
                raise NotImplementedError

        # TODO use loop context
        self.loop_body(post_loop, stop=number, loop_register=loop_register)

    def _add_wait_for_ent_info_cmd(self, ent_info_array, pair):
        """Wait for the correct slice of the entanglement info array for the given pair"""
        # NOTE arr_start should be pair * OK_FIELDS and
        # arr_stop should be (pair + 1) * OK_FIELDS
        arr_start = self._get_inactive_register(activate=True)
        tmp = self._get_inactive_register(activate=True)
        arr_stop = self._get_inactive_register(activate=True)
        created_regs = [arr_start, tmp, arr_stop]

        for reg in created_regs:
            self.add_pending_command(Command(
                instruction=Instruction.SET,
                operands=[reg, 0],
            ))

        # Multiply pair * OK_FIELDS
        # TODO use loop context
        def add_arr_start(conn):
            self.add_pending_command(Command(
                instruction=Instruction.ADD,
                operands=[arr_start, arr_start, pair],
            ))
        self.loop_body(add_arr_start, stop=OK_FIELDS)

        # Let tmp be pair + 1
        self.add_pending_command(Command(
            instruction=Instruction.ADD,
            operands=[tmp, pair, 1],
        ))

        # Multiply (tmp = pair + 1) * OK_FIELDS
        # TODO use loop context
        def add_arr_stop(conn):
            self.add_pending_command(Command(
                instruction=Instruction.ADD,
                operands=[arr_stop, arr_stop, tmp],
            ))
        self.loop_body(add_arr_stop, stop=OK_FIELDS)

        wait_cmd = Command(
            instruction=Instruction.WAIT_ALL,
            operands=[ArraySlice(ent_info_array.address, start=arr_start, stop=arr_stop)],
        )
        self.add_pending_command(wait_cmd)

        for reg in created_regs:
            self._remove_active_register(register=reg)

    def _handle_request(
        self,
        instruction,
        remote_node_id,
        epr_socket_id,
        number,
        post_routine,
        sequential,
        tp,
        random_basis_local=None,
        random_basis_remote=None,
    ):
        self._assert_epr_args(number=number, post_routine=post_routine, sequential=sequential, tp=tp)
        # NOTE the `output` is either a list of qubits or a list of entanglement information
        # depending on the type of the request.
        output, ent_info_array = self._handle_arguments(
            instruction=instruction,
            remote_node_id=remote_node_id,
            number=number,
            tp=tp,
            sequential=sequential,
        )
        if tp == EPRType.K:
            virtual_qubit_ids = [q.qubit_id for q in output]
        else:
            virtual_qubit_ids = None
        wait_all = post_routine is None
        qubit_ids_array = self._add_epr_commands(
            instruction=instruction,
            virtual_qubit_ids=virtual_qubit_ids,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
            number=number,
            ent_info_array=ent_info_array,
            wait_all=wait_all,
            tp=tp,
            random_basis_local=random_basis_local,
            random_basis_remote=random_basis_remote,
        )

        self._add_post_commands(qubit_ids_array, number, ent_info_array, tp, post_routine)

        return output

    def _pre_epr_context(self, instruction, remote_node_id, epr_socket_id, number=1, sequential=False, tp=EPRType.K):
        # NOTE since this is in a context there will be a post_routine
        self._assert_epr_args(number=number, post_routine=True, sequential=sequential, tp=tp)
        output, ent_info_array = self._handle_arguments(
            instruction=instruction,
            remote_node_id=remote_node_id,
            number=number,
            tp=tp,
            sequential=sequential,
        )
        if tp == EPRType.K:
            virtual_qubit_ids = [q.qubit_id for q in output]
        else:
            raise ValueError("EPR generation as a context is only allowed for K type requests")
        qubit_ids_array = self._add_epr_commands(
            instruction=instruction,
            virtual_qubit_ids=virtual_qubit_ids,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
            number=number,
            ent_info_array=ent_info_array,
            wait_all=False,
            tp=tp,
        )
        pre_commands = self._pop_pending_commands()
        loop_register = self._get_inactive_register(activate=True)
        pair = loop_register
        if tp == EPRType.K:
            q_id = qubit_ids_array.get_future_index(pair)
            q = _FutureQubit(conn=self, future_id=q_id)
            output = q
        # elif tp == EPRType.M:
        #     slc = slice(pair * OK_FIELDS, (pair + 1) * OK_FIELDS)
        #     ent_info_slice = ent_info_array.get_future_slice(slc)
        #     output = ent_info_slice
        else:
            raise NotImplementedError
        return pre_commands, loop_register, ent_info_array, output, pair

    def _post_epr_context(self, pre_commands, number, loop_register, ent_info_array, pair):
        body_commands = self._pop_pending_commands()
        self._add_wait_for_ent_info_cmd(
            ent_info_array=ent_info_array,
            pair=pair,
        )
        wait_cmds = self._pop_pending_commands()
        body_commands = wait_cmds + body_commands
        self._add_loop_commands(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=number,
            start=0,
            step=1,
            loop_register=loop_register,
        )
        self._remove_active_register(register=loop_register)

    def _assert_epr_args(self, number, post_routine, sequential, tp):
        assert isinstance(tp, EPRType), "tp is not an EPRType"
        if sequential and number > 1:
            if post_routine is None:
                raise ValueError("When using sequential mode with more than one pair "
                                 "a post_routine needs to be specified which consumes the "
                                 "generated pair as they come in.")
        if tp == EPRType.K and not sequential and number > self._max_qubits:
            raise ValueError(f"When not using sequential mode for K type, the number of pairs {number} cannot be "
                             f"greater than the maximum number of qubits specified ({self._max_qubits}).")

    def _handle_arguments(self, instruction, remote_node_id, number, tp, sequential):
        if instruction == Instruction.CREATE_EPR:
            self._logger.debug(f"App {self.app_name} puts command to create EPR with {remote_node_id}")
        elif instruction == Instruction.RECV_EPR:
            self._logger.debug(f"App {self.app_name} puts command to recv EPR from {remote_node_id}")
        else:
            raise ValueError(f"Not an epr instruction {instruction}")

        ent_info_array = self.new_array(length=OK_FIELDS * number)
        ent_info_slices = self._create_ent_info_slices(
            num_pairs=number,
            ent_info_array=ent_info_array,
            tp=tp,
        )
        if tp == EPRType.K:
            qubits = self._create_ent_qubits(
                ent_info_slices=ent_info_slices,
                sequential=sequential,
            )
            return qubits, ent_info_array
        elif tp == EPRType.M:
            return ent_info_slices, ent_info_array
        else:
            raise NotImplementedError

    def _create_ent_info_slices(self, num_pairs, ent_info_array, tp):
        ent_info_slices = []
        for i in range(num_pairs):
            ent_info_slice = ent_info_array.get_future_slice(slice(i * OK_FIELDS, (i + 1) * OK_FIELDS))
            ent_info_slice = self.__class__.ENT_INFO[tp](*ent_info_slice)
            ent_info_slices.append(ent_info_slice)
        return ent_info_slices

    def _create_ent_qubits(self, ent_info_slices, sequential):
        qubits = []
        virtual_address = None
        for i, ent_info_slice in enumerate(ent_info_slices):
            # If sequential we want all qubits to have the same ID
            if sequential:
                if i == 0:
                    qubit = Qubit(self, add_new_command=False, ent_info=ent_info_slice)
                    virtual_address = qubit.qubit_id
                else:
                    qubit = Qubit(self, add_new_command=False, ent_info=ent_info_slice, virtual_address=virtual_address)
            else:
                virtual_address = None
                if self._compiler == NVSubroutineCompiler:
                    # If compiling for NV, only virtual ID 0 can be used to store the entangled qubit.
                    # So, if this qubit is already in use, we need to move it away first.
                    virtual_address = 0
                self._free_up_qubit(virtual_address=virtual_address)
                qubit = Qubit(self, add_new_command=False, ent_info=ent_info_slice, virtual_address=virtual_address)
            qubits.append(qubit)

        return qubits

    def _create_epr(
        self,
        remote_node_id,
        epr_socket_id,
        number=1,
        post_routine=None,
        sequential=False,
        tp=EPRType.K,
        random_basis_local=None,
        random_basis_remote=None,
    ):
        """Receives EPR pair with a remote node"""
        if not isinstance(remote_node_id, int):
            raise TypeError(f"remote_node_id should be an int, not of type {type(remote_node_id)}")
        return self._handle_request(
            instruction=Instruction.CREATE_EPR,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
            number=number,
            post_routine=post_routine,
            sequential=sequential,
            tp=tp,
            random_basis_local=random_basis_local,
            random_basis_remote=random_basis_remote,
        )

    def _recv_epr(self, remote_node_id, epr_socket_id, number=1, post_routine=None, sequential=False, tp=EPRType.K):
        """Receives EPR pair with a remote node"""
        return self._handle_request(
            instruction=Instruction.RECV_EPR,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
            number=number,
            post_routine=post_routine,
            sequential=sequential,
            tp=tp,
        )

    def _get_new_qubit_address(self):
        qubit_addresses_in_use = [q.qubit_id for q in self.active_qubits]
        for address in count(0):
            if address not in qubit_addresses_in_use:
                return address

    def _get_new_array_address(self):
        used_addresses = self._used_array_addresses
        for address in count(0):
            if address not in used_addresses:
                used_addresses.append(address)
                return address

    def _reset(self):
        if len(self._active_registers) > 0:
            raise RuntimeError("Should not have active registers left when flushing")
        self._arrays_to_return = []
        self._registers_to_return = []
        self._used_meas_registers = []
        self._pre_context_commands = {}

    def if_eq(self, a, b, body):
        """An effective if-statement where body is a function executing the clause for a == b"""
        self._handle_if(Instruction.BEQ, a, b, body)

    def if_ne(self, a, b, body):
        """An effective if-statement where body is a function executing the clause for a != b"""
        self._handle_if(Instruction.BNE, a, b, body)

    def if_lt(self, a, b, body):
        """An effective if-statement where body is a function executing the clause for a < b"""
        self._handle_if(Instruction.BLT, a, b, body)

    def if_ge(self, a, b, body):
        """An effective if-statement where body is a function executing the clause for a >= b"""
        self._handle_if(Instruction.BGE, a, b, body)

    def if_ez(self, a, body):
        """An effective if-statement where body is a function executing the clause for a == 0"""
        self._handle_if(Instruction.BEZ, a, b=None, body=body)

    def if_nz(self, a, body):
        """An effective if-statement where body is a function executing the clause for a != 0"""
        self._handle_if(Instruction.BNZ, a, b=None, body=body)

    def _handle_if(self, condition, a, b, body):
        """Used to build effective if-statements"""
        current_commands = self._pop_pending_commands()
        body(self)
        body_commands = self._pop_pending_commands()
        self._add_if_statement_commands(
            pre_commands=current_commands,
            body_commands=body_commands,
            condition=condition,
            a=a,
            b=b,
        )

    def _add_if_statement_commands(self, pre_commands, body_commands, condition, a, b):
        if len(body_commands) == 0:
            self.add_pending_commands(commands=pre_commands)
            return
        branch_instruction = flip_branch_instr(condition)
        # Construct a list of all commands to see what branch labels are already used
        all_commands = pre_commands + body_commands
        # We also need to check any existing other pre context commands if they are nested
        for pre_context_cmds in self._pre_context_commands.values():
            all_commands += pre_context_cmds
        current_branch_variables = [
            cmd.name for cmd in all_commands if isinstance(cmd, BranchLabel)
        ]
        if_start, if_end = self._get_branch_commands(
            branch_instruction=branch_instruction,
            a=a,
            b=b,
            current_branch_variables=current_branch_variables,
        )
        commands = pre_commands + if_start + body_commands + if_end

        self.add_pending_commands(commands=commands)

    def _get_branch_commands(self, branch_instruction, a, b, current_branch_variables):
        # Exit label
        exit_label = self._find_unused_variable(start_with="IF_EXIT", current_variables=current_branch_variables)
        cond_values = []
        if_start = []
        for x in [a, b]:
            if isinstance(x, Future):
                # Register for checking branching based on condition
                reg = self._get_inactive_register(activate=True)
                # Load values
                address_entry = parse_address(f"{Symbols.ADDRESS_START}{x._address}[{x._index}]")
                load = Command(
                    instruction=Instruction.LOAD,
                    operands=[
                        reg,
                        address_entry,
                    ]
                )
                cond_values.append(reg)
                if_start.append(load)
            elif isinstance(x, RegFuture):
                cond_values.append(x.reg)
            elif isinstance(x, int):
                cond_values.append(x)
            else:
                raise TypeError(f"Cannot do conditional statement with type {type(x)}")
        branch = Command(
            instruction=branch_instruction,
            operands=[
                cond_values[0],
                cond_values[1],
                Label(exit_label),
            ]
        )
        if_start.append(branch)

        # Inactivate the temporary registers
        for val in cond_values:
            if isinstance(val, Register):
                if not val.name == RegisterName.M:  # M-registers are never temporary
                    self._remove_active_register(register=val)

        exit = BranchLabel(exit_label)
        if_end = [exit]

        return if_start, if_end

    @contextmanager
    def loop(self, stop, start=0, step=1, loop_register=None):
        try:
            pre_commands = self._pop_pending_commands()
            loop_register = self._handle_loop_register(loop_register, activate=True)
            yield loop_register
        finally:
            body_commands = self._pop_pending_commands()
            self._add_loop_commands(
                pre_commands=pre_commands,
                body_commands=body_commands,
                stop=stop,
                start=start,
                step=step,
                loop_register=loop_register,
            )
            self._remove_active_register(register=loop_register)

    def loop_body(self, body, stop, start=0, step=1, loop_register=None):
        """An effective loop-statement where body is a function executed, a number of times specified
        by `start`, `stop` and `step`.
        """
        loop_register = self._handle_loop_register(loop_register)

        pre_commands = self._pop_pending_commands()
        with self._activate_register(loop_register):
            body(self)
        body_commands = self._pop_pending_commands()
        self._add_loop_commands(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=stop,
            start=start,
            step=step,
            loop_register=loop_register,
        )

    def _add_loop_commands(self, pre_commands, body_commands, stop, start, step, loop_register):
        if len(body_commands) == 0:
            self.add_pending_commands(commands=pre_commands)
            return
        current_branch_variables = [
            cmd.name for cmd in pre_commands + body_commands if isinstance(cmd, BranchLabel)
        ]
        current_registers = get_current_registers(body_commands)
        loop_start, loop_end = self._get_loop_commands(
            start=start,
            stop=stop,
            step=step,
            current_branch_variables=current_branch_variables,
            current_registers=current_registers,
            loop_register=loop_register,
        )
        commands = pre_commands + loop_start + body_commands + loop_end

        self.add_pending_commands(commands=commands)

    def _handle_loop_register(self, loop_register, activate=False):
        if loop_register is None:
            loop_register = self._get_inactive_register(activate=activate)
        else:
            if isinstance(loop_register, Register):
                pass
            elif isinstance(loop_register, str):
                loop_register = parse_register(loop_register)
            else:
                raise ValueError(f"not a valid loop_register with type {type(loop_register)}")
            if loop_register in self._active_registers:
                raise ValueError("Register used for looping should not already be active")
        # self._add_active_register(loop_register)
        return loop_register

    def _get_inactive_register(self, activate=False):
        for i in range(2 ** REG_INDEX_BITS):
            register = parse_register(f"R{i}")
            if register not in self._active_registers:
                if activate:
                    self._add_active_register(register=register)
                return register
        raise RuntimeError("could not find an available loop register")

    @contextmanager
    def _activate_register(self, register):
        try:
            self._add_active_register(register=register)
            yield
        except Exception as err:
            raise err
        finally:
            self._remove_active_register(register=register)

    def _add_active_register(self, register):
        if register in self._active_registers:
            raise ValueError(f"Register {register} is already active")
        self._active_registers.add(register)

    def _remove_active_register(self, register):
        self._active_registers.remove(register)

    def _get_loop_commands(self, start, stop, step, current_branch_variables, current_registers, loop_register):
        entry_label = self._find_unused_variable(start_with="LOOP", current_variables=current_branch_variables)
        exit_label = self._find_unused_variable(start_with="LOOP_EXIT", current_variables=current_branch_variables)

        entry_loop, exit_loop = self._get_entry_exit_loop_cmds(
            start=start,
            stop=stop,
            step=step,
            entry_label=entry_label,
            exit_label=exit_label,
            loop_register=loop_register,
        )

        return entry_loop, exit_loop

    @staticmethod
    def _get_entry_exit_loop_cmds(start, stop, step, entry_label, exit_label, loop_register):
        entry_loop = [
            Command(
                instruction=Instruction.SET,
                operands=[loop_register, start],
            ),
            BranchLabel(entry_label),
            Command(
                instruction=Instruction.BEQ,
                operands=[
                    loop_register,
                    stop,
                    Label(exit_label),
                ],
            ),
        ]
        exit_loop = [
            Command(
                instruction=Instruction.ADD,
                operands=[
                    loop_register,
                    loop_register,
                    step,
                ],
            ),
            Command(
                instruction=Instruction.JMP,
                operands=[Label(entry_label)],
            ),
            BranchLabel(exit_label),
        ]
        return entry_loop, exit_loop

    @staticmethod
    def _find_unused_variable(start_with="", current_variables=None):
        if current_variables is None:
            current_variables = set([])
        else:
            current_variables = set(current_variables)
        if start_with not in current_variables:
            return start_with
        else:
            for i in count(1):
                var_name = f"{start_with}{i}"
                if var_name not in current_variables:
                    return var_name

    def _enter_if_context(self, context_id, condition, a, b):
        pre_commands = self._pop_pending_commands()
        self._pre_context_commands[context_id] = pre_commands

    def _exit_if_context(self, context_id, condition, a, b):
        body_commands = self._pop_pending_commands()
        pre_context_commands = self._pre_context_commands.pop(context_id, None)
        if pre_context_commands is None:
            raise RuntimeError("Something went wrong, no pre_context_commands")
        self._add_if_statement_commands(
            pre_commands=pre_context_commands,
            body_commands=body_commands,
            condition=condition,
            a=a,
            b=b,
        )

    def _enter_foreach_context(self, context_id, array, return_index):
        pre_commands = self._pop_pending_commands()
        loop_register = self._get_inactive_register(activate=True)
        self._pre_context_commands[context_id] = pre_commands, loop_register
        if return_index:
            return loop_register, array.get_future_index(loop_register)
        else:
            return array.get_future_index(loop_register)

    def _exit_foreach_context(self, context_id, array, return_index):
        body_commands = self._pop_pending_commands()
        pre_context_commands = self._pre_context_commands.pop(context_id, None)
        if pre_context_commands is None:
            raise RuntimeError("Something went wrong, no pre_context_commands")
        pre_commands, loop_register = pre_context_commands
        self._add_loop_commands(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=len(array),
            start=0,
            step=1,
            loop_register=loop_register,
        )
        self._remove_active_register(register=loop_register)

    def tomography(self, preparation, iterations, progress=True):
        """
        Does a tomography on the output from the preparation specified.
        The frequencies from X, Y and Z measurements are returned as a tuple (f_X,f_Y,f_Z).

        - **Arguments**

            :preparation:     A function that takes a NetQASMConnection as input and prepares a qubit and returns this
            :iterations:     Number of measurements in each basis.
            :progress_bar:     Displays a progress bar
        """
        outcomes = {"X": [], "Y": [], "Z": []}
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

    def test_preparation(self, preparation, exp_values, conf=2, iterations=100, progress=True):
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

    def _commit_serialized_message(self, raw_msg, block=True, callback=None):
        """Commit a message to the backend/qnodeos"""
        self.storage.append(raw_msg)

    def _get_network_info(self) -> Type[NetworkInfo]:
        return DebugNetworkInfo


class DebugNetworkInfo(NetworkInfo):
    @classmethod
    def _get_node_id(cls, node_name):
        """Returns the node id for the node with the given name"""
        node_id = DebugConnection.node_ids.get(node_name)
        if node_id is None:
            raise ValueError(f"{node_name} is not a known node name")
        return node_id

    @classmethod
    def _get_node_name(cls, node_id):
        """Returns the node name for the node with the given ID"""
        for n_name, n_id in DebugConnection.node_ids.items():
            if n_id == node_id:
                return n_name
        raise ValueError(f"{node_id} is not a known node ID")

    @classmethod
    def get_node_id_for_app(cls, app_name):
        """Returns the node id for the app with the given name"""
        return cls._get_node_id(node_name=app_name)

    @classmethod
    def get_node_name_for_app(cls, app_name):
        """Returns the node name for the app with the given name"""
        return app_name
