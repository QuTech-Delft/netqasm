import abc
import logging
from itertools import count
from collections import namedtuple

from cqc.pythonLib import CQCHandler
from cqc.cqcHeader import (
    CQC_CMD_NEW,
    CQC_CMD_X,
    CQC_CMD_Z,
    CQC_CMD_H,
    CQC_CMD_CNOT,
    CQC_CMD_MEASURE,
    CQC_CMD_RELEASE,
    CQC_CMD_EPR,
    CQC_CMD_EPR_RECV,
    command_to_string,
)

from netqasm import NETQASM_VERSION
from netqasm.parsing.text import assemble_subroutine
from netqasm.instructions import Instruction
from netqasm.sdk.shared_memory import get_shared_memory
from netqasm.sdk.qubit import Qubit
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
    CQC_CMD_Z: Instruction.Z,
    CQC_CMD_H: Instruction.H,
    CQC_CMD_CNOT: Instruction.CNOT,
    CQC_CMD_MEASURE: Instruction.MEAS,
    CQC_CMD_EPR: Instruction.CREATE_EPR,
    CQC_CMD_EPR_RECV: Instruction.RECV_EPR,
    CQC_CMD_RELEASE: Instruction.QFREE,
}


class NetQASMConnection(CQCHandler, abc.ABC):
    def __init__(self, name, app_id=None, max_qubits=5):
        super().__init__(name=name, app_id=app_id)

        self._used_array_addresses = []

        self._init_new_app(max_qubits=max_qubits)

        self._pending_commands = []

        # self._pending_subroutine = None

        self._shared_memory = get_shared_memory(self.name, key=self._appID)

        self._array_outcomes_address = None

        self._next_array_outcome_index = 0

        self._variables = {}

        self._logger = logging.getLogger(f"{self.__class__.__name__}({self.name})")

    @property
    def shared_memory(self):
        return self._shared_memory

    @property
    def array_outcomes_address(self):
        if self._array_outcomes_address is None:
            self._array_outcomes_address = self._get_new_array_address()
        return self._array_outcomes_address

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

    def createEPR(self, name, purpose_id=0, number=1, block=True):
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
        remote_node_id = self._get_remote_node_id(name)
        logging.debug(f"App {self.name} puts command to create EPR with {name}")
        qubits = [Qubit(self, put_new_command=False) for _ in range(number)]
        virtual_qubit_ids = [q._qID for q in qubits]
        self.put_command(
            qID=virtual_qubit_ids,
            command=CQC_CMD_EPR,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            number=number,
            block=block,
        )

        return qubits

    def recvEPR(self, name, purpose_id=0, number=1, block=True):
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
        remote_node_id = self._get_remote_node_id(name)
        logging.debug(f"App {self.name} puts command to recv EPR with {name}")
        qubits = [Qubit(self, put_new_command=False) for _ in range(number)]
        virtual_qubit_ids = [q._qID for q in qubits]
        self.put_command(
            qID=virtual_qubit_ids,
            command=CQC_CMD_EPR_RECV,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            number=number,
            block=block,
        )

        return qubits

    def _get_remote_node_id(self, name):
        raise NotImplementedError

    def put_command(self, qID, command, **kwargs):
        self._logger.debug(f"Put new command={command_to_string(command)} for qubit qID={qID} with kwargs={kwargs}")
        self._pending_commands.append(_Command(qID=qID, command=command, kwargs=kwargs))

    def flush(self, block=True):
        subroutine = self._pop_pending_subroutine()
        if subroutine is None:
            return

        self._commit_subroutine(subroutine=subroutine, block=block)

    def _commit_subroutine(self, subroutine, block=True):
        self._logger.debug(f"Flushing subroutine:\n{subroutine}")

        # Parse, assembly and possibly compile the subroutine
        bin_subroutine = self._pre_process_subroutine(subroutine)

        # Commit the subroutine to the quantum device
        self.commit(bin_subroutine, block=block)

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
        else:
            subroutine = None
        return subroutine

    def _subroutine_from_commands(self, commands):
        # Build sub-routine
        all_netqasm_commands = []
        for command in commands:
            netqasm_commands = self._get_netqasm_command(command)
            all_netqasm_commands += netqasm_commands
        metadata = self._get_metadata()
        return Subroutine(**metadata, commands=all_netqasm_commands)

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
        outcome_reg = self._conn._get_new_meas_outcome_reg()
        array_entry = command.kwargs.get('array_entry')
        q_address = command.qID
        qubit_reg, set_command = self._get_set_qubit_reg_command(q_address)
        meas_command = Command(
            instruction=Instruction.MEAS,
            operands=[qubit_reg, outcome_reg],
        )
        free_command = Command(
            instruction=Instruction.QFREE,
            operands=[Constant(q_address)],
        )
        if array_entry is not None:
            store_command = Command(
                instruction=Instruction.STORE,
                operands=[outcome_reg, array_entry],
            )
            return_command = Command(
                instruction=Instruction.RET_REG,
                operands=[outcome_reg],
            )
            outcome_commands = [store_command, return_command]
        else:
            outcome_commands = []
        return [set_command, meas_command, free_command] + outcome_commands

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
        entinfo_address = self._get_new_array_address()

        remote_node_id = command.kwargs["remote_node_id"]
        purpose_id = command.kwargs["purpose_id"]
        number = command.kwargs["number"]
        block = command.kwargs["block"]
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
            # arguments
            # TODO add other args
            # TODO num args should be specified elsewhere and not hardcoded here
            num_args = 20
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
            args_cmds = []
            epr_cmd_operands = [
                Constant(qubit_id_address),
                Constant(entinfo_address),
            ]
        else:
            raise ValueError(f"Not an epr command {command}")

        # entanglement information
        # TODO should be specified elsewhere and not hardcoded here
        num_values = 8
        ent_info_length = number * num_values
        ent_info_cmd = Command(
            instruction=Instruction.ARRAY,
            operands=[Constant(ent_info_length), Address(entinfo_address)],
        )
        # ent_info_cmd = f"{array}({number}) {at}{entinfo_address}\n"

        # epr command
        epr_cmd = Command(
            instruction=Instruction.CREATE_EPR,
            args=[Constant(remote_node_id), Constant(purpose_id)],
            operands=epr_cmd_operands,
        )
        # epr_cmd = (
        #     f"{instr}({remote_node_id}, {purpose_id}) "
        #     f"{at}{qubit_id_address}{arg_operand} {at}{entinfo_address}\n"
        # )
        # wait_cmd = f"{wait} {at}{entinfo_address}\n"
        if block:
            wait_cmds = [Command(
                instruction=Instruction.WAIT_ALL,
                operands=[ArraySlice(entinfo_address, start=0, stop=ent_info_length)],
            )]
        else:
            wait_cmds = []

        return (
            epr_address_cmds +
            args_cmds +
            [ent_info_cmd] +
            [epr_cmd] +
            wait_cmds
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

    def _create_new_outcome_variable(self, var_name):
        address = self.array_outcomes_address
        index = self._get_array_outcome_index(var_name=var_name)
        array_entry = ArrayEntry(address=address, index=index)
        self._set_variable(array_entry=array_entry, var_name=var_name)
        return array_entry

    def _set_variable(self, array_entry, var_name):
        self._variables[var_name] = array_entry

    def read_variable(self, var_name):
        array_entry = self._variables.get(var_name)
        if array_entry is None:
            raise ValueError(f"{var_name} is not a known name of a variable")
        return self._shared_memory.get_array_entry(array_entry=array_entry)

    def _get_array_outcome_index(self, var_name):
        """Finds a new index for a measurement outcome"""
        index = self._next_array_outcome_index
        self._next_array_outcome_index += 1
        return index

    def loop(self, body, end, start=0, var_address='i'):
        current_commands = self._pop_pending_commands()
        body(self)
        body_commands = self._pop_pending_commands()
        current_branch_variables = [cmd.name for cmd in current_commands + body_commands if isinstance(cmd, Label)]
        # current_branch_variables = _find_current_branch_variables(body_subroutine)
        loop_start, loop_end = self._get_loop_commands(
            start=start,
            end=end,
            var_address=var_address,
            current_branch_variables=current_branch_variables,
        )
        commands = current_commands + loop_start + body_commands + loop_end

        self._set_pending_commands(commands=commands)

    def _get_loop_commands(self, start, end, var_address, current_branch_variables):
        loop_variable = self._find_unused_variable(start_with="LOOP", current_variables=current_branch_variables)
        exit_variable = self._find_unused_variable(start_with="EXIT", current_variables=current_branch_variables)
        # start_loop = f"""store {var_address} {start}
# {loop_variable}:
# beq {var_address} {end} {exit_variable}
# """
        start_loop = [
            Command(
                instruction=Instruction.STORE,
                operands=[Register(RegisterName.R, 0), Constant(start)],
            ),
            BranchLabel(loop_variable),
            Command(
                instruction=Instruction.BEQ,
                operands=[
                    Register(RegisterName.R, 0),
                    Constant(end),
                    Label(loop_variable),
                ],
            ),
        ]
        # end_loop = f"""add {var_address} {var_address} 1
# beq 0 0 {loop_variable}
# {exit_variable}:
# """
        end_loop = [
            Command(
                instruction=Instruction.ADD,
                operands=[
                    Register(RegisterName.R, 0),
                    Register(RegisterName.R, 0),
                    Constant(0),
                ],
            ),
            Command(
                instruction=Instruction.JMP,
                operands=[Label(loop_variable)],
            ),
            BranchLabel(exit_variable),
        ]
        return start_loop, end_loop

    def _find_unused_variable(self, start_with="", current_variables=None):
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
