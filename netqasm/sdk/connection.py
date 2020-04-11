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
from netqasm.parsing.text import _find_current_branch_variables
from netqasm.instructions import Instruction, instruction_to_string
from netqasm.sdk.shared_memory import get_shared_memory
from netqasm.sdk.qubit import Qubit
from netqasm.subroutine import Symbols, Subroutine, Command, Register, Constant
from netqasm.encoding import RegisterName


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

        self._used_classical_addresses = []

        self._init_new_app(max_qubits=max_qubits)

        self._pending_commands = []

        self._pending_subroutine = None

        self._shared_memory = get_shared_memory(self.name, key=self._appID)

        self._logger = logging.getLogger(f"{self.__class__.__name__}({self.name})")

    @property
    def shared_memory(self):
        return self._shared_memory

    def new_qubitID(self):
        return self._get_new_qubit_address()

    def _handle_create_qubits(self, num_qubits):
        raise NotImplementedError

    def return_meas_outcome(self):
        raise NotImplementedError

    def _init_new_app(self, max_qubits):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        pass

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
        )

        return qubits

    def recvEPR(self, name, purpose_id=0, number=1):
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

    def _put_subroutine(self, subroutine):
        """Stores a subroutine to be flushed"""
        self._pending_subroutine = subroutine

    def _pop_pending_subroutine(self):
        if len(self._pending_commands) > 0 and self._pending_subroutine is not None:
            raise RuntimeError("There's both a pending subroutine and pending commands")
        if self._pending_subroutine is not None:
            subroutine = self._pending_subroutine
            self._pending_subroutine = None
        elif len(self._pending_commands) > 0:
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

    def _pre_process_subroutine(self, subroutine):
        """Parses and assembles the subroutine.

        Can be subclassed and overried for more elaborate compiling.
        """
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
            args=[],
            operands=[
                register,
            ],
        )
        return [set_command, qubit_command]

    def _get_set_qubit_reg_command(self, q_address, reg_index=0):
        # Set the register with the qubit address
        register = Register(RegisterName.Q, reg_index)
        set_command = Command(
            instruction=Instruction.SET,
            args=[],
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
            args=[],
            operands=[
                register1,
                register2,
            ],
        )
        return [set_command1, set_command2, qubit_command]

    def _get_netqasm_meas_command(self, command):
        outcome_reg = command.kwargs['outcome_reg']
        q_address = command.qID
        qubit_reg, set_command = self._get_set_qubit_reg_command(q_address)
        meas_command = Command(
            instruction=Instruction.MEAS,
            args=[],
            operands=[
                qubit_reg,
                outcome_reg,
            ],
        )
        free_command = Command(
            instruction=Instruction.QFREE,
            args=[],
            operands=[
                qubit_reg,
            ],
        )
        return [set_command, meas_command, free_command]

    def _get_netqasm_new_command(self, command):
        q_address = command.qID
        qubit_reg, set_command = self._get_set_qubit_reg_command(q_address)
        qalloc_command = Command(
            instruction=Instruction.QALLOC,
            args=[],
            operands=[
                qubit_reg,
            ],
        )
        init_command = Command(
            instruction=Instruction.INIT,
            args=[],
            operands=[
                qubit_reg,
            ],
        )
        return [set_command, qalloc_command, init_command]

    def _get_netqasm_epr_command(self, command):
        raise NotImplementedError()
        # TODO
        # epr_address_var = "epr_address"
        # ent_info_var = "ent_info"
        # arg_address_var = "arg_address"
        # TODO How to assign new classical addresses?
        qubit_id_address = self._get_new_classical_address()
        entinfo_address = self._get_new_classical_address()
        arg_address = self._get_new_classical_address()

        remote_node_id = command.kwargs["remote_node_id"]
        purpose_id = command.kwargs["purpose_id"]
        number = command.kwargs["number"]

        # instructions to use
        instr = _CQC_TO_NETQASM_INSTR[command.command]
        virtual_qubit_ids = command.qID
        store = instruction_to_string(Instruction.STORE)
        array = instruction_to_string(Instruction.ARRAY)
        wait = instruction_to_string(Instruction.WAIT)

        at = Symbols.ADDRESS_START

        # qubit addresses
        epr_address_cmds = f"{array}({number}) {at}{qubit_id_address}\n"
        for i in range(number):
            q_address = virtual_qubit_ids[i]
            epr_address_cmds += f"{store} {at}{qubit_id_address}[{i}] {q_address}\n"

        if command.command == CQC_CMD_EPR:
            # arguments
            # TODO
            num_args = 20
            args_cmds = f"{array}({num_args}) {at}{arg_address}\n"
            args_cmds += f"{store} {at}{arg_address}[1] {number} // number\n"
            arg_operand = f" {at}{arg_address}"
        elif command.command == CQC_CMD_EPR_RECV:
            args_cmds = ""
            arg_operand = ""
        else:
            raise ValueError(f"Not an epr command {command}")

        # entanglement information
        ent_info_cmd = f"{array}({number}) {at}{entinfo_address}\n"

        # epr command
        epr_cmd = (
            f"{instr}({remote_node_id}, {purpose_id}) "
            f"{at}{qubit_id_address}{arg_operand} {at}{entinfo_address}\n"
        )
        wait_cmd = f"{wait} {at}{entinfo_address}\n"

        return (
            epr_address_cmds +
            args_cmds +
            ent_info_cmd +
            epr_cmd +
            wait_cmd
        )

    def _get_netqasm_recv_epr_command(self, command):
        raise NotImplementedError()
        # TODO
        # epr_address_var = "epr_address"
        # ent_info_var = "ent_info"
        # TODO How to assign new classical addresses?
        epr_address_var = self._get_new_classical_address()
        ent_info_var = self._get_new_classical_address()

        virtual_qubit_ids = command.qID
        remote_node_id = command.kwargs["remote_node_id"]
        purpose_id = command.kwargs["purpose_id"]
        number = command.kwargs["number"]

        store = instruction_to_string(Instruction.STORE)
        array = instruction_to_string(Instruction.ARRAY)
        recv_epr = instruction_to_string(Instruction.RECV_EPR)
        wait = instruction_to_string(Instruction.WAIT)

        # qubit addresses
        epr_address_cmds = f"{array}({number}) {epr_address_var}\n"
        for i in range(number):
            q_address = virtual_qubit_ids[i]
            epr_address_cmds += f"{store} {epr_address_var}[{i}] {q_address}\n"

        # entanglement information
        ent_info_cmd = f"{array}({number}) {ent_info_var}\n"

        # create epr
        recv_epr_cmd = (
            f"{recv_epr}({remote_node_id}, {purpose_id}) "
            f"{epr_address_var} {ent_info_var}\n"
        )
        wait_cmd = f"{wait} {ent_info_var}\n"

        return (
            epr_address_cmds +
            ent_info_cmd +
            recv_epr_cmd +
            wait_cmd
        )

    def _handle_factory_response(self, num_iter, response_amount, should_notify=False):
        raise NotImplementedError

    def get_remote_from_directory_or_address(self, name, **kwargs):
        raise NotImplementedError

    def _handle_epr_response(self, notify):
        raise NotImplementedError

    def readMessage(self):
        raise NotImplementedError

    def _get_new_qubit_address(self):
        qubit_addresses_in_use = [q._qID for q in self.active_qubits]
        for address in count(0):
            if address not in qubit_addresses_in_use:
                return address

    def _get_new_classical_address(self):
        used_addresses = self._used_classical_addresses
        for address in count(0):
            if address not in used_addresses:
                used_addresses.append(address)
                return address

    def loop(self, body, end, start=0, var_address='i'):
        raise NotImplementedError
        body(self)
        body_subroutine = self._pop_pending_subroutine()
        current_branch_variables = _find_current_branch_variables(body_subroutine)
        loop_start, loop_end = self._get_loop_commands(
            start=start,
            end=end,
            var_address=var_address,
            current_branch_variables=current_branch_variables,
        )
        subroutine = loop_start + body_subroutine + loop_end

        self._put_subroutine(subroutine=subroutine)

    def _get_loop_commands(self, start, end, var_address, current_branch_variables):
        loop_variable = self._find_unused_variable(start_with="LOOP", current_variables=current_branch_variables)
        exit_variable = self._find_unused_variable(start_with="EXIT", current_variables=current_branch_variables)
        start_loop = f"""store {var_address} {start}
{loop_variable}:
beq {var_address} {end} {exit_variable}
"""
        end_loop = f"""add {var_address} {var_address} 1
beq 0 0 {loop_variable}
{exit_variable}:
"""
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
