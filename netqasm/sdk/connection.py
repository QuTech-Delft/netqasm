import abc
import logging
from itertools import count
from collections import namedtuple

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
    CQC_CMD_MEASURE,
    CQC_CMD_RELEASE,
    CQC_CMD_EPR,
    CQC_CMD_EPR_RECV,
    # command_to_string,
)

from netqasm import NETQASM_VERSION
from netqasm.parsing.text import assemble_subroutine, parse_register
from netqasm.instructions import Instruction
from netqasm.sdk.shared_memory import get_shared_memory
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.futures import Future, Array
from netqasm.network_stack import CREATE_FIELDS, OK_FIELDS
from netqasm.encoding import RegisterName
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
    CQC_CMD_MEASURE: Instruction.MEAS,
    CQC_CMD_EPR: Instruction.CREATE_EPR,
    CQC_CMD_EPR_RECV: Instruction.RECV_EPR,
    CQC_CMD_RELEASE: Instruction.QFREE,
}


class NetQASMConnection(CQCHandler, abc.ABC):

    # Class to use to pack entanglement information
    ENT_INFO = tuple

    def __init__(self, name, app_id=None, max_qubits=5):
        super().__init__(name=name, app_id=app_id)

        self._used_array_addresses = []

        self._init_new_app(max_qubits=max_qubits)

        self._pending_commands = []

        self._shared_memory = get_shared_memory(self.name, key=self._appID)

        # TODO
        # self._array_outcomes_address = None

        # self._next_array_outcome_index = 0

        # Registers for looping
        self._current_loop_registers = []

        # Arrays to return
        self._arrays_to_return = []

        # TODO
        # Used while building up a subroutine (until flushing)
        # self._variables = {}

        # TODO
        # Used after flushing
        # self._stored_variables = {}

        self._logger = logging.getLogger(f"{self.__class__.__name__}({self.name})")

    @property
    def shared_memory(self):
        return self._shared_memory

    # TODO
    # @property
    # def array_outcomes_address(self):
    #     if self._array_outcomes_address is None:
    #         self._array_outcomes_address = self._get_new_array_address()
    #     return self._array_outcomes_address

    def new_qubitID(self):
        return self._get_new_qubit_address()

    def _handle_create_qubits(self, num_qubits):
        # NOTE this is to comply with CQC abstract class
        raise NotImplementedError

    def return_meas_outcome(self):
        # NOTE this is to comply with CQC abstract class
        raise NotImplementedError

    def _init_new_app(self, max_qubits):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        pass

    def new_array(self, length):
        address = self._get_new_array_address()
        array = Array(
            connection=self,
            length=length,
            address=address,
        )
        self._arrays_to_return.append(array)
        return array

    def createEPR(self, name, purpose_id=0, number=1):
        """Creates EPR pair with a remote node""

        Parameters
        ----------
        name : str
            Name of the remote node
        purpose_id : int
            The purpose id for the entanglement generation
        number : int
            The number of pairs to create
        """
        # if entinfo_var_name is None:
        #     entinfo_var_name = self._get_unused_variable(start_with="entinfo")
        # entinfo_array_address = self._create_new_entinfo_variable(var_name=entinfo_var_name)
        entinfo_array_address = self._get_new_array_address()
        # ent_info = self._create_ent_info(entinfo_array_address)
        remote_node_id = self._get_remote_node_id(name)
        logging.debug(f"App {self.name} puts command to create EPR with {name}")
        # qubits = [Qubit(self, put_new_command=False, ent_info=ent_info) for _ in range(number)]
        qubits = self._create_ent_qubits(num_pairs=number, entinfo_array_address=entinfo_array_address)
        virtual_qubit_ids = [q._qID for q in qubits]
        self.put_command(
            qID=virtual_qubit_ids,
            command=CQC_CMD_EPR,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            number=number,
            entinfo_array_address=entinfo_array_address,
        )

        return qubits

    def _create_ent_qubits(self, num_pairs, entinfo_array_address):
        qubits = []
        index = 0
        for _ in range(num_pairs):
            ent_info = []
            for _ in range(OK_FIELDS):
                # TODO
                # entinfo_var_name = self._get_unused_variable(start_with="entinfo")
                # self._set_variable(address=entinfo_array_address, index=index, var_name=entinfo_var_name)
                index += 1
                ent_info.append(Future(self, address=entinfo_array_address, index=index))
            ent_info = self.__class__.ENT_INFO(*ent_info)
            qubit = Qubit(self, put_new_command=False, ent_info=ent_info)
            qubits.append(qubit)
        return qubits

    # def _create_new_entinfo_variable(self, var_name):
    #     address = self._get_new_array_address()
    #     self._set_variable(address=address, index=None, var_name=var_name)

    def recvEPR(self, name, purpose_id=0, number=1, entinfo_var_name=None):
        """Receives EPR pair with a remote node""

        Parameters
        ----------
        name : str
            Name of the remote node
        purpose_id : int
            The purpose id for the entanglement generation
        number : int
            The number of pairs to recv
        """
        # if entinfo_var_name is None:
        #     entinfo_var_name = self._get_unused_variable(start_with="entinfo")
        # entinfo_array_address = self._create_new_entinfo_variable(var_name=entinfo_var_name)
        entinfo_array_address = self._get_new_array_address()
        # ent_info = self._create_ent_info(entinfo_array_address)
        remote_node_id = self._get_remote_node_id(name)
        logging.debug(f"App {self.name} puts command to recv EPR with {name}")
        # qubits = [Qubit(self, put_new_command=False, ent_info) for _ in range(number)]
        qubits = self._create_ent_qubits(num_pairs=number, entinfo_array_address=entinfo_array_address)
        virtual_qubit_ids = [q._qID for q in qubits]
        self.put_command(
            qID=virtual_qubit_ids,
            command=CQC_CMD_EPR_RECV,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            number=number,
            entinfo_array_address=entinfo_array_address,
        )

        return qubits

    def _get_remote_node_id(self, name):
        raise NotImplementedError

    def _get_remote_node_name(self, remote_node_id):
        raise NotImplementedError

    def put_commands(self, commands, **kwargs):
        for command in commands:
            self.put_command(command, **kwargs)

    def put_command(self, command, **kwargs):
        if isinstance(command, Command):
            pass
        else:
            qID = kwargs["qID"]
            command = _Command(qID=qID, command=command, kwargs=kwargs)
        self._logger.debug(f"Put new command={command}")
        self._pending_commands.append(command)

    def flush(self, block=True):
        subroutine = self._pop_pending_subroutine()
        if subroutine is None:
            return

        self._commit_subroutine(subroutine=subroutine, block=block)

    def _commit_subroutine(self, subroutine, block=True):
        # TODO
        self._logger.info(f"Flushing subroutine:\n{subroutine}")

        # Parse, assembly and possibly compile the subroutine
        bin_subroutine = self._pre_process_subroutine(subroutine)

        # Commit the subroutine to the quantum device
        self.commit(bin_subroutine, block=block)

        self._reset()

    # def _put_subroutine(self, subroutine):
    #     """Stores a subroutine to be flushed"""
    #     self._pending_subroutine = subroutine

    def _pop_pending_subroutine(self):
        # if len(self._pending_commands) > 0 and self._pending_subroutine is not None:
        #     raise RuntimeError("There's both a pending subroutine and pending commands")
        # if self._pending_subroutine is not None:
        #     subroutine = self._pending_subroutine
        #     self._pending_subroutine = None
        if len(self._pending_commands) > 0:
            commands = self._pop_pending_commands()
            subroutine = self._subroutine_from_commands(commands)

            array_commands = self._get_array_commands()
            init_arrays, return_arrays = array_commands
            subroutine.commands = init_arrays + subroutine.commands + return_arrays

            # TODO
            # Allocate and return array of meas outcomes
            # outcome_array_commands = self._get_outcome_array_commands()
            # if outcome_array_commands is not None:
            #     outcome_array_cmd, return_outcomes_cmd = outcome_array_commands
            #     subroutine.commands.insert(0, outcome_array_cmd)
            #     subroutine.commands.append(return_outcomes_cmd)
        else:
            subroutine = None
        return subroutine

    def _get_array_commands(self):
        init_arrays = []
        return_arrays = []
        for array in self._arrays_to_return:
            init_arrays.append(Command(
                instruction=Instruction.ARRAY,
                operands=[
                    Constant(len(array)),
                    Address(Constant(array.address)),
                ],
            ))
            return_arrays.append(Command(
                instruction=Instruction.RET_ARR,
                operands=[
                    Address(Constant(array.address)),
                ],
            ))
        return init_arrays, return_arrays

    def _subroutine_from_commands(self, commands):
        # Build sub-routine
        all_netqasm_commands = []
        for command in commands:
            if isinstance(command, _Command):
                netqasm_commands = self._get_netqasm_command(command)
                all_netqasm_commands += netqasm_commands
            else:
                all_netqasm_commands.append(command)
        metadata = self._get_metadata()
        return Subroutine(**metadata, commands=all_netqasm_commands)

    # TODO
    # def _get_outcome_array_commands(self):
    #     num_vars = len(self._variables)
    #     if num_vars == 0:
    #         return None
    #     array_address = self.array_outcomes_address
    #     array_command = Command(
    #         instruction=Instruction.ARRAY,
    #         operands=[Constant(num_vars), Address(Constant(array_address))],
    #     )
    #     return_command = Command(
    #         instruction=Instruction.RET_ARR,
    #         operands=[Address(Constant(array_address))],
    #     )
    #     return array_command, return_command

    def _get_metadata(self):
        return {
            "netqasm_version": NETQASM_VERSION,
            "app_id": self._appID,
        }

    def _pop_pending_commands(self):
        commands = self._pending_commands
        self._pending_commands = []
        return commands

    def _set_pending_commands(self, commands):
        self._pending_commands = commands

    def _pre_process_subroutine(self, subroutine):
        """Parses and assembles the subroutine.

        Can be subclassed and overried for more elaborate compiling.
        """
        subroutine = assemble_subroutine(subroutine)
        return bytes(subroutine)

    @abc.abstractmethod
    def commit(self, msg):
        pass

    def _get_netqasm_command(self, command):
        if command.command == CQC_CMD_MEASURE:
            return self._get_netqasm_meas_command(command)
        if command.command == CQC_CMD_NEW:
            return self._get_netqasm_new_command(command)
        if command.command in [CQC_CMD_EPR, CQC_CMD_EPR_RECV]:
            return self._get_netqasm_epr_command(command)
        if command.command in [CQC_CMD_CNOT]:
            return self._get_netqasm_two_qubit_command(command)
        else:
            return self._get_netqasm_single_qubit_command(command)

    def _get_netqasm_single_qubit_command(self, command):
        q_address = command.qID
        register, set_command = self._get_set_qubit_reg_command(q_address)
        # Construct the qubit command
        instr = _CQC_TO_NETQASM_INSTR[command.command]
        qubit_command = Command(
            instruction=instr,
            operands=[register],
        )
        return [set_command, qubit_command]

    def _get_set_qubit_reg_command(self, q_address, reg_index=0):
        # Set the register with the qubit address
        register = Register(RegisterName.Q, reg_index)
        set_command = Command(
            instruction=Instruction.SET,
            operands=[
                register,
                Constant(q_address),
            ],
        )
        return register, set_command

    def _get_netqasm_two_qubit_command(self, command):
        q_address1 = command.qID
        q_address2 = command.kwargs["xtra_qID"]
        register1, set_command1 = self._get_set_qubit_reg_command(q_address1, reg_index=0)
        register2, set_command2 = self._get_set_qubit_reg_command(q_address2, reg_index=1)
        instr = _CQC_TO_NETQASM_INSTR[command.command]
        qubit_command = Command(
            instruction=instr,
            operands=[register1, register2],
        )
        return [set_command1, set_command2, qubit_command]

    def _get_netqasm_meas_command(self, command):
        outcome_reg = self._get_new_meas_outcome_reg()
        address = command.kwargs.get('address')
        index = command.kwargs.get('index')
        inplace = command.kwargs.get('inplace')
        q_address = command.qID
        qubit_reg, set_command = self._get_set_qubit_reg_command(q_address)
        meas_command = Command(
            instruction=Instruction.MEAS,
            operands=[qubit_reg, outcome_reg],
        )
        if not inplace:
            free_commands = [Command(
                instruction=Instruction.QFREE,
                operands=[Constant(q_address)],
            )]
        else:
            free_commands = []
        if address is not None:
            # address, index = address_index
            store_command = Command(
                instruction=Instruction.STORE,
                operands=[outcome_reg, ArrayEntry(address=address, index=index)],
            )
            # TODO move to array func
            # return_command = Command(
            #     instruction=Instruction.RET_REG,
            #     operands=[outcome_reg],
            # )
            outcome_commands = [store_command]
        else:
            outcome_commands = []
        return [set_command, meas_command] + free_commands + outcome_commands

    def _get_new_meas_outcome_reg(self):
        # NOTE We can simply use the same every time (M0) since it will anyway be stored to memory if returned
        return Register(RegisterName.M, 0)

    def _get_netqasm_new_command(self, command):
        q_address = command.qID
        qubit_reg, set_command = self._get_set_qubit_reg_command(q_address)
        qalloc_command = Command(
            instruction=Instruction.QALLOC,
            operands=[qubit_reg],
        )
        init_command = Command(
            instruction=Instruction.INIT,
            operands=[qubit_reg],
        )
        return [set_command, qalloc_command, init_command]

    def _get_netqasm_epr_command(self, command):
        # TODO How to assign new array addresses?
        qubit_id_address = self._get_new_array_address()
        arg_address = self._get_new_array_address()
        # entinfo_address = self._get_new_array_address()

        remote_node_id = command.kwargs["remote_node_id"]
        purpose_id = command.kwargs["purpose_id"]
        number = command.kwargs["number"]
        entinfo_address = command.kwargs["entinfo_array_address"]
        virtual_qubit_ids = command.qID

        # # instructions to use
        # instr = _CQC_TO_NETQASM_INSTR[command.command]
        # store = instruction_to_string(Instruction.STORE)
        # array = instruction_to_string(Instruction.ARRAY)
        # wait = instruction_to_string(Instruction.WAIT)

        # at = Symbols.ADDRESS_START

        # qubit addresses
        # epr_address_cmds = f"{array}({number}) {at}{qubit_id_address}\n"
        epr_address_cmds = [Command(
            instruction=Instruction.ARRAY,
            operands=[Constant(number), Address(qubit_id_address)]
        )]
        for i in range(number):
            q_address = virtual_qubit_ids[i]
            # f"{store} {q_address} {at}{qubit_id_address}[{i}]\n"
            epr_address_cmds.append(Command(
                instruction=Instruction.STORE,
                operands=[Constant(q_address), ArrayEntry(qubit_id_address, i)],
            ))

        # create_operands = {}
        if command.command == CQC_CMD_EPR:
            instruction = Instruction.CREATE_EPR
            # arguments
            # TODO add other args
            num_args = CREATE_FIELDS
            # args_cmds = f"{array}({num_args}) {at}{arg_address}\n"
            # TODO don't create a new array if already created from previous command
            args_cmds = [Command(
                instruction=Instruction.ARRAY,
                operands=[Constant(num_args), Address(arg_address)],
            )]
            # args_cmds += f"{store} {number} {at}{arg_address}[1] // num pairs\n"
            args_cmds.append(Command(
                instruction=Instruction.STORE,
                operands=[Constant(number), ArrayEntry(arg_address, index=1)],
            ))
            # create_operands[
            # arg_operand = f" {arg_address}"
            epr_cmd_operands = [
                Constant(qubit_id_address),
                Constant(arg_address),
                Constant(entinfo_address),
            ]
        elif command.command == CQC_CMD_EPR_RECV:
            instruction = Instruction.RECV_EPR
            args_cmds = []
            epr_cmd_operands = [
                Constant(qubit_id_address),
                Constant(entinfo_address),
            ]
        else:
            raise ValueError(f"Not an epr command {command}")

        # entanglement information
        # TODO should be specified elsewhere and not hardcoded here
        num_values = OK_FIELDS
        ent_info_length = number * num_values
        ent_info_cmd = Command(
            instruction=Instruction.ARRAY,
            operands=[Constant(ent_info_length), Address(entinfo_address)],
        )
        # ent_info_cmd = f"{array}({number}) {at}{entinfo_address}\n"

        # Return entanglement information

        # epr command
        epr_cmd = Command(
            instruction=instruction,
            args=[Constant(remote_node_id), Constant(purpose_id)],
            operands=epr_cmd_operands,
        )
        # epr_cmd = (
        #     f"{instr}({remote_node_id}, {purpose_id}) "
        #     f"{at}{qubit_id_address}{arg_operand} {at}{entinfo_address}\n"
        # )
        # wait_cmd = f"{wait} {at}{entinfo_address}\n"
        wait_cmd = Command(
            instruction=Instruction.WAIT_ALL,
            operands=[ArraySlice(entinfo_address, start=0, stop=ent_info_length)],
        )

        # return ent info command
        return_cmd = Command(
            instruction=Instruction.RET_ARR,
            operands=[Address(Constant(entinfo_address))],
        )

        return (
            epr_address_cmds +
            args_cmds +
            [
                ent_info_cmd,
                epr_cmd,
                wait_cmd,
                return_cmd,
            ]
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

    # TODO
    # def _create_new_outcome_variable(self, var_name):
    #     address = self.array_outcomes_address
    #     index = self._get_array_outcome_index(var_name=var_name)
    #     self._set_variable(address=address, index=index, var_name=var_name)
    #     return address, index

    # def _set_variable(self, address, index, var_name):
    #     self._variables[var_name] = (address, index)

    # def read_variable(self, var_name):
    #     address_index = self._stored_variables.get(var_name)
    #     if address_index is None:
    #         raise ValueError(f"{var_name} is not a known name of a variable")
    #     address, index = address_index
    #     return self._shared_memory.get_array_part(address=address, index=index)

    # def _get_unused_variable(self, start_with="var"):
    #     for i in count(0):
    #         var_name = f"{start_with}{i}"
    #         if var_name not in self._variables:
    #             return var_name

    # def _get_array_outcome_index(self, var_name):
    #     """Finds a new index for a measurement outcome"""
    #     index = self._next_array_outcome_index
    #     self._next_array_outcome_index += 1
    #     return index

    def _reset(self):
        # TODO
        # self._array_outcomes_address = None
        # self._stored_variables = self._variables
        # self._variables = {}
        # self._next_array_outcome_index = 0
        self._current_loop_registers = []
        self._arrays_to_return = []

    def loop(self, body, stop, start=0, step=1, loop_register=None):
        current_commands = self._pop_pending_commands()
        body(self)
        body_commands = self._pop_pending_commands()
        current_branch_variables = [
                cmd.name for cmd in current_commands + body_commands if isinstance(cmd, BranchLabel)
        ]
        # current_branch_variables = _find_current_branch_variables(body_subroutine)
        loop_start, loop_end = self._get_loop_commands(
            start=start,
            stop=stop,
            step=step,
            current_branch_variables=current_branch_variables,
            loop_register=loop_register,
        )
        commands = current_commands + loop_start + body_commands + loop_end

        self._set_pending_commands(commands=commands)

    def _get_loop_commands(self, start, stop, step, current_branch_variables, loop_register):
        entry_variable = self._find_unused_variable(start_with="LOOP", current_variables=current_branch_variables)
        exit_variable = self._find_unused_variable(start_with="EXIT", current_variables=current_branch_variables)

        loop_register = self._handle_loop_register(loop_register)

        entry_loop, exit_loop = self._get_entry_exit_loop_cmds(
            start=start,
            stop=stop,
            step=step,
            entry_variable=entry_variable,
            exit_variable=exit_variable,
            loop_register=loop_register,
        )

        return entry_loop, exit_loop

    def _handle_loop_register(self, loop_register):
        if loop_register is None:
            loop_register = self._get_unused_loop_register()
        else:
            if isinstance(loop_register, Register):
                pass
            elif isinstance(loop_register, str):
                loop_register = parse_register(loop_register)
            else:
                raise ValueError(f"not a valid loop_register with type {type(loop_register)}")
            if loop_register in self._current_loop_registers:
                raise RuntimeError(f"register {loop_register} is already used for looping")
        self._current_loop_registers.append(loop_register)
        return loop_register

    @staticmethod
    def _get_entry_exit_loop_cmds(start, stop, step, entry_variable, exit_variable, loop_register):
        entry_loop = [
            Command(
                instruction=Instruction.SET,
                operands=[loop_register, Constant(start)],
            ),
            BranchLabel(entry_variable),
            Command(
                instruction=Instruction.BEQ,
                operands=[
                    loop_register,
                    Constant(stop),
                    Label(exit_variable),
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
                operands=[Label(entry_variable)],
            ),
            BranchLabel(exit_variable),
        ]
        return entry_loop, exit_loop

    def _get_unused_loop_register(self):
        for i in range(5):
            register = parse_register(f"R{i}")
            if register not in self._current_loop_registers:
                return register
        raise RuntimeError(f"could not find an available loop register (cannot do more than 5 nested loops)")

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
