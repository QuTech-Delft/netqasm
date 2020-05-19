import os
import abc
import pickle
import warnings
from itertools import count
from collections import namedtuple
from contextlib import contextmanager

from cqc.pythonLib import CQCHandler
from cqc.cqcHeader import (
    CQC_CMD_NEW,
    CQC_CMD_X,
    CQC_CMD_Y,
    CQC_CMD_Z,
    CQC_CMD_H,
    CQC_CMD_K,
    CQC_CMD_T,
    CQC_CMD_CNOT,
    CQC_CMD_CPHASE,
    CQC_CMD_MEASURE,
    CQC_CMD_RELEASE,
    CQC_CMD_EPR,
    CQC_CMD_EPR_RECV,
)

from netqasm import NETQASM_VERSION
from netqasm.logging import get_netqasm_logger
from netqasm.parsing.text import assemble_subroutine, parse_register, get_current_registers, parse_address
from netqasm.instructions import Instruction, flip_branch_instr
from netqasm.sdk.shared_memory import get_shared_memory
from netqasm.sdk.qubit import Qubit, _FutureQubit
from netqasm.sdk.futures import Future, Array
from netqasm.sdk.epr_socket import EPRType
from netqasm.sdk.toolbox import get_angle_spec_from_float
from netqasm.log_util import LineTracker
from netqasm.network_stack import CREATE_FIELDS, OK_FIELDS
from netqasm.encoding import RegisterName, REG_INDEX_BITS
from netqasm.subroutine import (
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
from netqasm.messages import (
    Signal,
    Message,
    InitNewAppMessage,
    MessageType,
    StopAppMessage,
    OpenEPRSocketMessage,
)


_Command = namedtuple("Command", ["qID", "command", "kwargs"])


_CQC_TO_NETQASM_INSTR = {
    CQC_CMD_NEW: Instruction.INIT,
    CQC_CMD_X: Instruction.X,
    CQC_CMD_Y: Instruction.K,
    CQC_CMD_Z: Instruction.Z,
    CQC_CMD_H: Instruction.H,
    CQC_CMD_K: Instruction.K,
    CQC_CMD_T: Instruction.T,
    CQC_CMD_CNOT: Instruction.CNOT,
    CQC_CMD_CPHASE: Instruction.CPHASE,
    CQC_CMD_MEASURE: Instruction.MEAS,
    CQC_CMD_EPR: Instruction.CREATE_EPR,
    CQC_CMD_EPR_RECV: Instruction.RECV_EPR,
    CQC_CMD_RELEASE: Instruction.QFREE,
}
_CQC_EPR_INSTRS = [
    CQC_CMD_EPR,
    CQC_CMD_EPR_RECV,
]
_CQC_SINGLE_Q_INSTRS = [
    CQC_CMD_NEW,
    CQC_CMD_X,
    CQC_CMD_Y,
    CQC_CMD_Z,
    CQC_CMD_H,
    CQC_CMD_K,
    CQC_CMD_T,
    CQC_CMD_RELEASE,
]
_CQC_TWO_Q_INSTRS = [
    CQC_CMD_CNOT,
    CQC_CMD_CPHASE,
]


# NOTE this is needed to be able to instanciate tuples the same way as namedtuples
class _Tuple(tuple):
    @classmethod
    def __new__(cls, *args, **kwargs):
        return tuple.__new__(cls, args[1:])


class NetQASMConnection(CQCHandler, abc.ABC):

    # Class to use to pack entanglement information
    ENT_INFO = {
        EPRType.K: _Tuple,
        EPRType.M: _Tuple,
        EPRType.R: _Tuple,
    }

    def __init__(
        self,
        name,
        app_id=None,
        max_qubits=5,
        track_lines=False,
        log_subroutines_dir=None,
        epr_sockets=None,
        compiler=None,
    ):
        super().__init__(name=name, app_id=app_id)

        self._used_array_addresses = []

        self._max_qubits = max_qubits
        self._init_new_app(max_qubits=max_qubits)

        self._pending_commands = []

        self._shared_memory = get_shared_memory(self.name, key=self._appID)

        # Registers for looping etc.
        # These are registers that are for example currently hold data and should
        # not be used for something else.
        # For example a register used for looping.
        self._active_registers = set()

        # Arrays to return
        self._arrays_to_return = []

        # Storing commands before an conditional statement
        self._pre_context_commands = {}

        # Can be set to false for e.g. debugging, not exposed to user atm
        self._clear_app_on_exit = True
        self._stop_backend_on_exit = True

        self._line_tracker = LineTracker(level=3, track_lines=track_lines)
        self._track_lines = track_lines

        # Should subroutines commited be saved for logging/debugging
        self._log_subroutines_dir = log_subroutines_dir
        # Commited subroutines saved for logging/debugging
        self._commited_subroutines = []

        # What compiler (if any) to be used
        self._compiler = compiler

        # Setup epr sockets
        self._setup_epr_sockets(epr_sockets=epr_sockets)

        self._logger = get_netqasm_logger(f"{self.__class__.__name__}({self.name})")

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Allow to not clear the app or stop the backend upon exit, for debugging and post processing
        self.close(
            clear_app=self._clear_app_on_exit,
            stop_backend=self._stop_backend_on_exit,
        )

    def close(self, clear_app=True, stop_backend=True):
        """Handle exiting of context."""
        # Flush all pending commands
        self.flush()

        self._pop_app_id()

        self._signal_stop(clear_app=clear_app, stop_backend=stop_backend)
        self._inactivate_qubits()

        if self._log_subroutines_dir is not None:
            self._save_log_subroutines()

    @abc.abstractmethod
    def _commit_message(self, msg, block=False):
        """Commit a message to the backend/qnodeos"""
        # Should be subclassed
        pass

    @abc.abstractmethod
    def _get_node_id(self, node_name):
        """Returns the node id for the node with the given name"""
        # Should be subclassed
        pass

    @abc.abstractmethod
    def _get_node_name(self, node_id):
        """Returns the node name for the node with the given ID"""
        # Should be subclassed
        pass

    def _inactivate_qubits(self):
        while len(self.active_qubits) > 0:
            q = self.active_qubits.pop()
            q._set_active(False)

    def _signal_stop(self, clear_app=True, stop_backend=True):
        if clear_app:
            self._commit_message(msg=Message(
                type=MessageType.STOP_APP,
                msg=StopAppMessage(app_id=self._appID),
            ))

        if stop_backend:
            self._commit_message(msg=Message(
                type=MessageType.SIGNAL,
                msg=Signal.STOP,
            ))

    def _save_log_subroutines(self):
        filename = f'subroutines_{self.name}.pkl'
        filepath = os.path.join(self._log_subroutines_dir, filename)
        with open(filepath, 'wb') as f:
            pickle.dump(self._commited_subroutines, f)

    @property
    def shared_memory(self):
        return self._shared_memory

    def new_qubitID(self):
        return self._get_new_qubit_address()

    def _handle_create_qubits(self, num_qubits):
        # NOTE this is to comply with CQC abstract class
        raise NotImplementedError

    def return_meas_outcome(self):
        # NOTE this is to comply with CQC abstract class
        raise NotImplementedError

    def commit(self):
        # NOTE this is to comply with CQC abstract class
        raise NotImplementedError

    def _init_new_app(self, max_qubits):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        self._commit_message(msg=Message(
            type=MessageType.INIT_NEW_APP,
            msg=InitNewAppMessage(
                app_id=self._appID,
                max_qubits=max_qubits,
            ),
        ))

    def _setup_epr_sockets(self, epr_sockets):
        if epr_sockets is None:
            return
        for epr_socket in epr_sockets:
            if epr_socket._remote_node_name == self.name:
                raise ValueError("A node cannot setup an EPR socket with itself")
            epr_socket.conn = self
            self._setup_epr_socket(
                epr_socket_id=epr_socket._epr_socket_id,
                remote_node_id=epr_socket._remote_node_id,
                remote_epr_socket_id=epr_socket._remote_epr_socket_id,
            )

    def _setup_epr_socket(self, epr_socket_id, remote_node_id, remote_epr_socket_id):
        """Sets up a new epr socket"""
        self._commit_message(msg=Message(
            type=MessageType.OPEN_EPR_SOCKET,
            msg=OpenEPRSocketMessage(
                epr_socket_id=epr_socket_id,
                remote_node_id=remote_node_id,
                remote_epr_socket_id=remote_epr_socket_id,
            ),
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

    def put_commands(self, commands, **kwargs):
        calling_lineno = self._line_tracker.get_line()
        for command in commands:
            if command.lineno is None:
                command.lineno = calling_lineno
            self.put_command(command, **kwargs)

    # TODO this should be reworked when not inherit from CQC anymore
    # Currently the name of this function is confusing
    def put_command(self, command, **kwargs):
        if isinstance(command, Command) or isinstance(command, BranchLabel):
            if command.lineno is None:
                command.lineno = self._line_tracker.get_line()
            self._pending_commands.append(command)
        else:
            self._put_netqasm_commands(command, **kwargs)

    def flush(self, block=True):
        subroutine = self._pop_pending_subroutine()
        if subroutine is None:
            return

        self._commit_subroutine(subroutine=subroutine, block=block)

    def _commit_subroutine(self, subroutine, block=True):
        self._logger.info(f"Flushing subroutine:\n{subroutine}")

        # Parse, assembly and possibly compile the subroutine
        bin_subroutine = self._pre_process_subroutine(subroutine)

        # Commit the subroutine to the quantum device
        self._logger.debug(f"Puts the next subroutine:\n{subroutine}")
        self._commit_message(
            msg=Message(type=MessageType.SUBROUTINE, msg=bin_subroutine),
            block=block,
        )

        self._reset()

    def _pop_pending_subroutine(self):
        # Add commands for initialising and returning arrays
        self._put_array_commands()
        if len(self._pending_commands) > 0:
            commands = self._pop_pending_commands()
            subroutine = self._subroutine_from_commands(commands)
        else:
            subroutine = None
        return subroutine

    def _put_array_commands(self):
        current_commands = self._pop_pending_commands()
        array_commands = self._get_array_commands()
        init_arrays, return_arrays = array_commands
        commands = init_arrays + current_commands + return_arrays
        self.put_commands(commands=commands)

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
            return_arrays.append(Command(
                instruction=Instruction.RET_ARR,
                operands=[
                    Address(array.address),
                ],
                lineno=array.lineno,
            ))
        return init_arrays, return_arrays

    def _subroutine_from_commands(self, commands):
        # Build sub-routine
        metadata = self._get_metadata()
        return Subroutine(**metadata, commands=commands)

    def _get_metadata(self):
        return {
            "netqasm_version": NETQASM_VERSION,
            "app_id": self._appID,
        }

    def _pop_pending_commands(self):
        commands = self._pending_commands
        self._pending_commands = []
        return commands

    def _pre_process_subroutine(self, subroutine):
        """Parses and assembles the subroutine.

        Can be subclassed and overried for more elaborate compiling.
        """
        subroutine = assemble_subroutine(subroutine)
        if self._compiler is not None:
            self._compiler.compile(subroutine=subroutine)
        if self._track_lines:
            self._log_subroutine(subroutine=subroutine)
        return bytes(subroutine)

    def _log_subroutine(self, subroutine):
        self._commited_subroutines.append(subroutine)

    def block(self):
        """Block until flushed subroutines finish"""
        raise NotImplementedError

    def _single_qubit_rotation(self, instruction, virtual_qubit_id, n=0, d=0, angle=None):
        if angle is not None:
            nds = get_angle_spec_from_float(angle=angle)
            for n, d in nds:
                self._single_qubit_rotation(
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
        self.put_commands(commands)

    # TODO stop using qID (not pep8) when not inheriting from CQC anymore
    def _put_netqasm_commands(self, command, **kwargs):
        if command == CQC_CMD_MEASURE:
            self._put_netqasm_meas_command(command=command, **kwargs)
        elif command == CQC_CMD_NEW:
            self._put_netqasm_new_command(command=command, **kwargs)
        elif command in _CQC_EPR_INSTRS:
            # NOTE shouldn't happen anymore
            raise RuntimeError("Didn't expect a EPR command from CQC, should directly be a NetQASM command.")
            # self._put_netqasm_epr_command(command=command, **kwargs)
        elif command in _CQC_TWO_Q_INSTRS:
            self._put_netqasm_two_qubit_command(command=command, **kwargs)
        elif command in _CQC_SINGLE_Q_INSTRS:
            self._put_netqasm_single_qubit_command(command=command, **kwargs)
        else:
            raise ValueError(f"Unknown cqc instruction {command}")

    def _put_netqasm_single_qubit_command(self, command, qID, **kwargs):
        q_address = qID
        register, set_commands = self._get_set_qubit_reg_commands(q_address)
        # Construct the qubit command
        if isinstance(command, Instruction):
            instr = command
        else:
            instr = _CQC_TO_NETQASM_INSTR[command]
        qubit_command = Command(
            instruction=instr,
            operands=[register],
        )
        commands = set_commands + [qubit_command]
        self.put_commands(commands)

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

    def _put_netqasm_two_qubit_command(self, command, qID, xtra_qID, **kwargs):
        q_address1 = qID
        q_address2 = xtra_qID
        register1, set_commands1 = self._get_set_qubit_reg_commands(q_address1, reg_index=0)
        register2, set_commands2 = self._get_set_qubit_reg_commands(q_address2, reg_index=1)
        instr = _CQC_TO_NETQASM_INSTR[command]
        qubit_command = Command(
            instruction=instr,
            operands=[register1, register2],
        )
        commands = set_commands1 + set_commands2 + [qubit_command]
        self.put_commands(commands=commands)

    def _put_netqasm_meas_command(self, command, qID, future, inplace, **kwargs):
        outcome_reg = self._get_new_meas_outcome_reg()
        q_address = qID
        qubit_reg, set_commands = self._get_set_qubit_reg_commands(q_address)
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
            outcome_commands = future._get_store_commands(outcome_reg)
        else:
            outcome_commands = []
        commands = set_commands + [meas_command] + free_commands + outcome_commands
        self.put_commands(commands)

    def _get_new_meas_outcome_reg(self):
        # NOTE We can simply use the same every time (M0) since it will anyway be stored to memory if returned
        return Register(RegisterName.M, 0)

    def _put_netqasm_new_command(self, command, qID, **kwargs):
        q_address = qID
        qubit_reg, set_commands = self._get_set_qubit_reg_commands(q_address)
        qalloc_command = Command(
            instruction=Instruction.QALLOC,
            operands=[qubit_reg],
        )
        init_command = Command(
            instruction=Instruction.INIT,
            operands=[qubit_reg],
        )
        commands = set_commands + [qalloc_command, init_command]
        self.put_commands(commands)

    def _put_epr_commands(
        self,
        instruction,
        virtual_qubit_ids,
        remote_node_id,
        epr_socket_id,
        number,
        ent_info_array,
        wait_all,
        tp,
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
            # arguments
            # TODO add other args
            num_args = CREATE_FIELDS
            # TODO don't create a new array if already created from previous command
            create_args = [None] * num_args
            create_args[0] = tp.value  # Type, i.e. K, M or R
            create_args[1] = number  # Number of pairs
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
        self.put_commands(commands)

        return qubit_ids_array

    def _put_post_commands(self, qubit_ids, number, ent_info_array, tp, post_routine=None):
        if post_routine is None:
            return []

        loop_register = self._get_inactive_register()

        def post_loop(conn):
            # Wait for each pair individually
            pair = loop_register
            conn._put_wait_for_ent_info_cmd(
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

    def _put_wait_for_ent_info_cmd(self, ent_info_array, pair):
        """Wait for the correct slice of the entanglement info array for the given pair"""
        # NOTE arr_start should be pair * OK_FIELDS and
        # arr_stop should be (pair + 1) * OK_FIELDS
        arr_start = self._get_inactive_register(activate=True)
        tmp = self._get_inactive_register(activate=True)
        arr_stop = self._get_inactive_register(activate=True)
        created_regs = [arr_start, tmp, arr_stop]

        for reg in created_regs:
            self.put_command(Command(
                instruction=Instruction.SET,
                operands=[reg, 0],
            ))

        # Multiply pair * OK_FIELDS
        # TODO use loop context
        def add_arr_start(conn):
            self.put_command(Command(
                instruction=Instruction.ADD,
                operands=[arr_start, arr_start, pair],
            ))
        self.loop_body(add_arr_start, stop=OK_FIELDS)

        # Let tmp be pair + 1
        self.put_command(Command(
            instruction=Instruction.ADD,
            operands=[tmp, pair, 1],
        ))

        # Multiply (tmp = pair + 1) * OK_FIELDS
        # TODO use loop context
        def add_arr_stop(conn):
            self.put_command(Command(
                instruction=Instruction.ADD,
                operands=[arr_stop, arr_stop, tmp],
            ))
        self.loop_body(add_arr_stop, stop=OK_FIELDS)

        wait_cmd = Command(
            instruction=Instruction.WAIT_ALL,
            operands=[ArraySlice(ent_info_array.address, start=arr_start, stop=arr_stop)],
        )
        self.put_command(wait_cmd)

        for reg in created_regs:
            self._remove_active_register(register=reg)

    def _handle_request(self, instruction, remote_node_id, epr_socket_id, number, post_routine, sequential, tp):
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
            virtual_qubit_ids = [q._qID for q in output]
        else:
            virtual_qubit_ids = None
        wait_all = post_routine is None
        qubit_ids_array = self._put_epr_commands(
            instruction=instruction,
            virtual_qubit_ids=virtual_qubit_ids,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
            number=number,
            ent_info_array=ent_info_array,
            wait_all=wait_all,
            tp=tp,
        )

        self._put_post_commands(qubit_ids_array, number, ent_info_array, tp, post_routine)

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
            virtual_qubit_ids = [q._qID for q in output]
        else:
            raise ValueError("EPR generation as a context is only allowed for K type requests")
        qubit_ids_array = self._put_epr_commands(
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
        self._put_wait_for_ent_info_cmd(
            ent_info_array=ent_info_array,
            pair=pair,
        )
        wait_cmds = self._pop_pending_commands()
        body_commands = wait_cmds + body_commands
        self._put_loop_commands(
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
            self._logger.debug(f"App {self.name} puts command to create EPR with {remote_node_id}")
        elif instruction == Instruction.RECV_EPR:
            self._logger.debug(f"App {self.name} puts command to recv EPR from {remote_node_id}")
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
                    qubit = Qubit(self, put_new_command=False, ent_info=ent_info_slice)
                    virtual_address = qubit._qID
                else:
                    qubit = Qubit(self, put_new_command=False, ent_info=ent_info_slice, virtual_address=virtual_address)
            else:
                qubit = Qubit(self, put_new_command=False, ent_info=ent_info_slice)
            qubits.append(qubit)
        return qubits

    def createEPR(self, remote_node_name, epr_socket_id=0, **kwargs):
        """Receives EPR pair with a remote node

        NOTE: this method is deprecated and :class:`~.sdk.epr_socket.EPRSocket` should be used instead.
        """
        warnings.warn(
            "This function is deprecated, use the `netqasm.sdk.EPRSocket`-class instead.",
            DeprecationWarning,
        )
        remote_node_id = self._get_node_id(node_name=remote_node_name)
        return self._create_epr(remote_node_id=remote_node_id, epr_socket_id=epr_socket_id, **kwargs)

    def _create_epr(self, remote_node_id, epr_socket_id, number=1, post_routine=None, sequential=False, tp=EPRType.K):
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
        )

    def recvEPR(self, remote_node_name, epr_socket_id=0, **kwargs):
        """Receives EPR pair with a remote node

        NOTE: this method is deprecated and :class:`~.sdk.epr_socket.EPRSocket` should be used instead.
        """
        warnings.warn(
            "This function is deprecated, use the `netqasm.sdk.EPRSocket`-class instead.",
            DeprecationWarning,
        )
        remote_node_id = self._get_node_id(node_name=remote_node_name)
        return self._recv_epr(remote_node_id=remote_node_id, epr_socket_id=epr_socket_id, **kwargs)

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

    def _handle_factory_response(self, num_iter, response_amount, should_notify=False):
        # NOTE this is to comply with CQC abstract class
        raise NotImplementedError

    def get_remote_from_directory_or_address(self, name, **kwargs):
        # NOTE this is to comply with CQC abstract class
        raise NotImplementedError

    def _handle_epr_response(self, notify):
        # NOTE this is to comply with CQC abstract class
        raise NotImplementedError

    def readMessage(self):
        # NOTE this is to comply with CQC abstract class
        raise NotImplementedError

    def _get_new_qubit_address(self):
        qubit_addresses_in_use = [q._qID for q in self.active_qubits]
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
        self._handle_if(Instruction.BEZ, a, b=None, body=body)

    def _handle_if(self, condition, a, b, body):
        """Used to build effective if-statements"""
        current_commands = self._pop_pending_commands()
        body(self)
        body_commands = self._pop_pending_commands()
        self._put_if_statement_commands(
            pre_commands=current_commands,
            body_commands=body_commands,
            condition=condition,
            a=a,
            b=b,
        )

    def _put_if_statement_commands(self, pre_commands, body_commands, condition, a, b):
        if len(body_commands) == 0:
            self.put_commands(commands=pre_commands)
            return
        branch_instruction = flip_branch_instr(condition)
        current_branch_variables = [
                cmd.name for cmd in pre_commands + body_commands if isinstance(cmd, BranchLabel)
        ]
        if_start, if_end = self._get_branch_commands(
            branch_instruction=branch_instruction,
            a=a,
            b=b,
            current_branch_variables=current_branch_variables,
        )
        commands = pre_commands + if_start + body_commands + if_end

        self.put_commands(commands=commands)

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
            self._put_loop_commands(
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
        self._put_loop_commands(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=stop,
            start=start,
            step=step,
            loop_register=loop_register,
        )

    def _put_loop_commands(self, pre_commands, body_commands, stop, start, step, loop_register):
        if len(body_commands) == 0:
            self.put_commands(commands=pre_commands)
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

        self.put_commands(commands=commands)

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
        raise RuntimeError(f"could not find an available loop register")

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
        self._put_if_statement_commands(
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
        self._put_loop_commands(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=len(array),
            start=0,
            step=1,
            loop_register=loop_register,
        )
        self._remove_active_register(register=loop_register)


class DebugConnection(NetQASMConnection):

    node_ids = {}

    def __init__(self, *args, **kwargs):
        """A connection that simply stores the subroutine it commits"""
        self.storage = []
        super().__init__(*args, **kwargs)

    def _commit_message(self, msg, block=False):
        """Commit a message to the backend/qnodeos"""
        self.storage.append(msg)

    def _get_node_id(self, node_name):
        """Returns the node id for the node with the given name"""
        node_id = self.__class__.node_ids.get(node_name)
        if node_id is None:
            raise ValueError(f"{node_name} is not a known node name")
        return node_id

    def _get_node_name(self, node_id):
        """Returns the node name for the node with the given ID"""
        for n_name, n_id in self.__class__.node_ids.items():
            if n_id == node_id:
                return n_name
        raise ValueError(f"{node_id} is not a known node ID")
