import os
import abc
import pickle
import inspect
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
from netqasm.util import NoCircuitRuleError
from netqasm.parsing.text import assemble_subroutine, parse_register, get_current_registers, parse_address
from netqasm.instructions import Instruction, flip_branch_instr
from netqasm.sdk.shared_memory import get_shared_memory
from netqasm.sdk.qubit import Qubit, _FutureQubit
from netqasm.sdk.futures import Future, Array
from netqasm.network_stack import CREATE_FIELDS, OK_FIELDS, Rule, CircuitRules
from netqasm.encoding import RegisterName, REG_INDEX_BITS
from netqasm.subroutine import (
    Subroutine,
    Command,
    Register,
    Constant,
    Address,
    ArrayEntry,
    ArraySlice,
    Label,
    BranchLabel,
    Symbols,
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


class LineTracker:
    def __init__(self, track_lines=True):
        self._track_lines = track_lines
        if not self._track_lines:
            return
        # Get the file-name of the calling host application
        frame = inspect.currentframe()
        for _ in range(3):
            frame = frame.f_back
        self._calling_filename = self._get_file_from_frame(frame)

    def _get_file_from_frame(self, frame):
        return str(frame).split(',')[1][7:-1]

    def get_line(self):
        if not self._track_lines:
            return None
        frame = inspect.currentframe()
        while True:
            if self._get_file_from_frame(frame) == self._calling_filename:
                break
            frame = frame.f_back
        else:
            raise RuntimeError(f"Different calling file than {self._calling_filename}")
        return frame.f_lineno


class NetQASMConnection(CQCHandler, abc.ABC):

    # Class to use to pack entanglement information
    ENT_INFO = _Tuple

    def __init__(
        self,
        name,
        app_id=None,
        max_qubits=5,
        track_lines=False,
        log_subroutines_dir=None,
        epr_to=None,
        epr_from=None,
    ):
        super().__init__(name=name, app_id=app_id)

        self._used_array_addresses = []

        self._circuit_rules = self._get_circuit_rules(epr_to=epr_to, epr_from=epr_from)

        self._max_qubits = max_qubits
        self._init_new_app(max_qubits=max_qubits, circuit_rules=self._circuit_rules)

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
        self._stop_backend_on_exit = True

        self._line_tracker = LineTracker(track_lines)
        self._track_lines = track_lines

        # Should subroutines commited be saved for logging/debugging
        self._log_subroutines_dir = log_subroutines_dir
        # Commited subroutines saved for logging/debugging
        self._commited_subroutines = []

        self._logger = get_netqasm_logger(f"{self.__class__.__name__}({self.name})")

    def _get_circuit_rules(self, epr_to=None, epr_from=None):
        if epr_to is None and epr_from is None:
            return CircuitRules(create_rules=[], recv_rules=[])
        # Should be subclassed, is implemented in squidasm.sdk.NetSquidConnection
        raise NotImplementedError

    def _assert_has_rule(self, tp, remote_node_id, purpose_id):
        if tp == 'create':
            rules = self._circuit_rules.create_rules
        elif tp == 'recv':
            rules = self._circuit_rules.recv_rules
        else:
            raise ValueError(f"{tp} is not a known rule type")
        rule = Rule(remote_node_id=remote_node_id, purpose_id=purpose_id)
        if rule not in rules:
            raise NoCircuitRuleError("Cannot create/recv entanglement with node "
                                     f"with ID {remote_node_id} and purpose ID {purpose_id}.\n"
                                     "Declare this by using the arguments `epr_to` and/or `epr_from` "
                                     "to the connection.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Allow to not stop the backend upon exit, for future use-cases
        self.close(stop_backend=self._stop_backend_on_exit)

    def close(self, stop_backend=True):
        """Handle exiting of context."""
        # Flush all pending commands
        self.flush()

        self._pop_app_id()

        self._signal_stop(stop_backend=stop_backend)
        self._inactivate_qubits()

        if self._track_lines:
            self._save_log_subroutines()

    def _inactivate_qubits(self):
        while len(self.active_qubits) > 0:
            q = self.active_qubits.pop()
            q._set_active(False)

    def _signal_stop(self, stop_backend=True):
        # Should be overriden to indicate to backend that the applications is stopping
        pass

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

    def _init_new_app(self, max_qubits, circuit_rules=None):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        pass

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

    def createEPR(self, name, purpose_id=0, number=1, post_routine=None, sequential=False):
        """Creates EPR pair with a remote node

        Parameters
        ----------
        name : str
            Name of the remote node
        purpose_id : int
            The purpose id for the entanglement generation
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
        return self._handle_epr_request(
            instruction=Instruction.CREATE_EPR,
            name=name,
            purpose_id=purpose_id,
            number=number,
            post_routine=post_routine,
            sequential=sequential,
        )

    def _handle_epr_request(self, instruction, name, purpose_id, number, post_routine, sequential):
        self._assert_epr_args(number=number, post_routine=post_routine, sequential=sequential)
        qubits, remote_node_id, ent_info_array = self._handle_epr_arguments(
            instruction=instruction,
            name=name,
            number=number,
            purpose_id=purpose_id,
            sequential=sequential,
        )
        virtual_qubit_ids = [q._qID for q in qubits]
        wait_all = post_routine is None
        qubit_ids_array = self._put_epr_commands(
            instruction=instruction,
            virtual_qubit_ids=virtual_qubit_ids,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            number=number,
            ent_info_array=ent_info_array,
            wait_all=wait_all,
        )

        self._put_post_commands(qubit_ids_array, number, ent_info_array, post_routine)

        return qubits

    @contextmanager
    def create_epr_context(self, name, purpose_id=0, number=1, sequential=False):
        try:
            instruction = Instruction.CREATE_EPR
            pre_commands, loop_register, ent_info_array, q, pair = self._pre_epr_context(
                instruction=instruction,
                name=name,
                purpose_id=purpose_id,
                number=number,
                sequential=sequential,
            )
            yield q, pair
        finally:
            self._post_epr_context(
                pre_commands=pre_commands,
                number=number,
                loop_register=loop_register,
                ent_info_array=ent_info_array,
                pair=pair,
            )

    def _pre_epr_context(self, instruction, name, purpose_id=0, number=1, sequential=False):
        # NOTE since this is in a context there will be a post_routine
        self._assert_epr_args(number=number, post_routine=True, sequential=sequential)
        qubits, remote_node_id, ent_info_array = self._handle_epr_arguments(
            instruction=instruction,
            name=name,
            number=number,
            purpose_id=purpose_id,
            sequential=sequential,
        )
        virtual_qubit_ids = [q._qID for q in qubits]
        qubit_ids_array = self._put_epr_commands(
            instruction=instruction,
            virtual_qubit_ids=virtual_qubit_ids,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            number=number,
            ent_info_array=ent_info_array,
            wait_all=False,
        )
        pre_commands = self._pop_pending_commands()
        loop_register = self._get_inactive_register(activate=True)
        pair = loop_register
        q_id = qubit_ids_array.get_future_index(pair)
        q = _FutureQubit(conn=self, future_id=q_id)
        return pre_commands, loop_register, ent_info_array, q, pair

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

    def _assert_epr_args(self, number, post_routine, sequential):
        if sequential and number > 1:
            if post_routine is None:
                raise ValueError("When using sequential mode with more than one pair "
                                 "a post_routine needs to be specified which consumes the "
                                 "generated pair as they come in.")
        if not sequential and number > self._max_qubits:
            raise ValueError(f"When not using sequential mode, the number of pairs {number} cannot be "
                             f"greater than the maximum number of qubits specified ({self._max_qubits}).")

    def _create_ent_qubits(self, num_pairs, ent_info_array, sequential):
        qubits = []
        virtual_address = None
        for i in range(num_pairs):
            ent_info = ent_info_array.get_future_slice(slice(i * OK_FIELDS, (i + 1) * OK_FIELDS))
            ent_info = self.__class__.ENT_INFO(*ent_info)
            if i == 0:
                qubit = Qubit(self, put_new_command=False, ent_info=ent_info)
                virtual_address = qubit._qID
            else:
                qubit = Qubit(self, put_new_command=False, ent_info=ent_info, virtual_address=virtual_address)
            qubits.append(qubit)
        return qubits

    def recvEPR(self, name, purpose_id=0, number=1, post_routine=None, sequential=False):
        """Receives EPR pair with a remote node""

        Parameters
        ----------
        name : str
            Name of the remote node
        purpose_id : int
            The purpose id for the entanglement generation
        number : int
            The number of pairs to recv
        post_routine : function
            See description for :meth:`~.createEPR`
        """
        return self._handle_epr_request(
            instruction=Instruction.RECV_EPR,
            name=name,
            purpose_id=purpose_id,
            number=number,
            post_routine=post_routine,
            sequential=sequential,
        )

    @contextmanager
    def recv_epr_context(self, name, purpose_id=0, number=1, sequential=False):
        try:
            instruction = Instruction.RECV_EPR
            pre_commands, loop_register, ent_info_array, q, pair = self._pre_epr_context(
                instruction=instruction,
                name=name,
                purpose_id=purpose_id,
                number=number,
                sequential=sequential,
            )
            yield q, pair
        finally:
            self._post_epr_context(
                pre_commands=pre_commands,
                number=number,
                loop_register=loop_register,
                ent_info_array=ent_info_array,
                pair=pair,
            )

    def _get_remote_node_id(self, name):
        raise NotImplementedError

    def _get_remote_node_name(self, remote_node_id):
        raise NotImplementedError

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
        self.commit(bin_subroutine, block=block)

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
                    Constant(len(array)),
                    Address(Constant(array.address)),
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
                            Constant(value),
                            ArrayEntry(Address(Constant(array.address)), i),
                        ],
                        lineno=array.lineno,
                    ))
            # Command for returning the array by the end of the subroutine
            return_arrays.append(Command(
                instruction=Instruction.RET_ARR,
                operands=[
                    Address(Constant(array.address)),
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
        if self._track_lines:
            self._log_subroutine(subroutine=subroutine)
        return bytes(subroutine)

    def _log_subroutine(self, subroutine):
        self._commited_subroutines.append(subroutine)

    @abc.abstractmethod
    def commit(self, msg, block=True):
        pass

    def block(self):
        """Block until flushed subroutines finish"""
        raise NotImplementedError

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
                    Constant(q_address),
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

    def _handle_epr_arguments(self, instruction, name, number, purpose_id, sequential):
        if instruction == Instruction.CREATE_EPR:
            self._logger.debug(f"App {self.name} puts command to create EPR with {name}")
            rule_tp = 'create'
        elif instruction == Instruction.RECV_EPR:
            self._logger.debug(f"App {self.name} puts command to recv EPR from {name}")
            rule_tp = 'recv'
        else:
            raise ValueError(f"Not an epr instruction {instruction}")

        remote_node_id = self._get_remote_node_id(name)
        self._assert_has_rule(tp=rule_tp, remote_node_id=remote_node_id, purpose_id=purpose_id)
        ent_info_array = self.new_array(length=OK_FIELDS * number)
        qubits = self._create_ent_qubits(
            num_pairs=number,
            ent_info_array=ent_info_array,
            sequential=sequential,
        )
        return qubits, remote_node_id, ent_info_array

    def _put_epr_commands(
        self,
        instruction,
        virtual_qubit_ids,
        remote_node_id,
        purpose_id,
        number,
        ent_info_array,
        wait_all,
        **kwargs,
    ):
        # qubit addresses
        qubit_ids_array = self.new_array(init_values=virtual_qubit_ids)

        if instruction == Instruction.CREATE_EPR:
            # arguments
            # TODO add other args
            num_args = CREATE_FIELDS
            # TODO don't create a new array if already created from previous command
            create_args = [None] * num_args
            create_args[1] = number  # Number of pairs
            create_args_array = self.new_array(init_values=create_args)
            epr_cmd_operands = [
                Constant(qubit_ids_array.address),
                Constant(create_args_array.address),
                Constant(ent_info_array.address),
            ]
        elif instruction == Instruction.RECV_EPR:
            epr_cmd_operands = [
                Constant(qubit_ids_array.address),
                Constant(ent_info_array.address),
            ]
        else:
            raise ValueError(f"Not an epr instruction {instruction}")

        # epr command
        epr_cmd = Command(
            instruction=instruction,
            args=[Constant(remote_node_id), Constant(purpose_id)],
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

    def _put_post_commands(self, qubit_ids, number, ent_info_array, post_routine=None):
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
            q_id = qubit_ids.get_future_index(pair)
            q = _FutureQubit(conn=conn, future_id=q_id)
            post_routine(self, q, pair)

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
                operands=[reg, Constant(0)],
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
            operands=[tmp, pair, Constant(1)],
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
                cond_values.append(Constant(x))
            elif isinstance(x, Constant):
                cond_values.append(x.value)
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
                operands=[loop_register, Constant(start)],
            ),
            BranchLabel(entry_label),
            Command(
                instruction=Instruction.BEQ,
                operands=[
                    loop_register,
                    Constant(stop),
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
                    Constant(step),
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

    _node_ids = {}

    @classmethod
    def set_node_ids(cls, node_ids):
        """Used to set node IDs for node names in a network for this debug connection"""
        cls._node_ids = node_ids

    def __init__(self, *args, **kwargs):
        """A connection that simply stores the subroutine it commits"""
        super().__init__(*args, **kwargs)
        self.storage = []

    def commit(self, subroutine, block=True):
        self.storage.append(subroutine)

    def _get_circuit_rules(self, epr_to=None, epr_from=None):
        # Don't do anything for this debug connection
        pass

    def _get_remote_node_id(self, name):
        node_id = self.__class__._node_ids.get(name)
        if node_id is None:
            raise ValueError(f"node {name} is not known")
        return node_id

    def _assert_has_rule(self, tp, remote_node_id, purpose_id):
        pass
