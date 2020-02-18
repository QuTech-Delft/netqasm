import abc
import logging
from itertools import count
from collections import namedtuple, defaultdict

from cqc.pythonLib import CQCHandler
from cqc.cqcHeader import (
    CQC_CMD_NEW,
    CQC_CMD_X,
    CQC_CMD_H,
    CQC_CMD_MEASURE,
    CQC_CMD_RELEASE,
    command_to_string,
)

from netqasm import NETQASM_VERSION
from netqasm.parser import Parser, Subroutine
from netqasm.encoder import Instruction, instruction_to_string


_Command = namedtuple("Command", ["qID", "command", "kwargs"])


_CQC_TO_NETQASM_INSTR = {
    CQC_CMD_NEW: instruction_to_string(Instruction.INIT),
    CQC_CMD_X: instruction_to_string(Instruction.X),
    CQC_CMD_H: instruction_to_string(Instruction.H),
    CQC_CMD_MEASURE: instruction_to_string(Instruction.MEAS),
    CQC_CMD_RELEASE: instruction_to_string(Instruction.QFREE),
}


class NetQASMConnection(CQCHandler, abc.ABC):
    def __init__(self, name, app_id=None):
        super().__init__(name=name, app_id=app_id)


        self._used_quantum_addresses = []

        self._used_quantum_reg_indices = defaultdict(list)
        self._used_classical_reg_indices = defaultdict(list)

        self._unallocated_qubit_indices = []

        self._current_quantum_register_address = self._get_new_quantum_register_address()
        self._current_classical_register_address = self._get_shared_classical_register_address()

        self._pending_commands = []

        self._logger = logging.getLogger(f"{self.__class__.__name__}({self.name})")

    def close(self, release_qubits=True, release_bits=True):
        super().close(release_qubits=release_qubits)

    def new_qubitID(self):
        return (
            self._current_quantum_register_address,
            self._get_new_quantum_reg_index(),
        )

    def _handle_create_qubits(self, num_qubits):
        raise NotImplementedError

    def return_meas_outcome(self):
        raise NotImplementedError

    def put_command(self, qID, command, **kwargs):
        self._logger.debug(f"Put new command={command_to_string(command)} for qubit qID={qID} with kwargs={kwargs}")
        self._pending_commands.append(_Command(qID=qID, command=command, kwargs=kwargs))

    def flush(self, block=True):
        if len(self._pending_commands) == 0:
            return
        # Build sub-routine
        subroutine = ""
        subroutine += self._get_subroutine_preamble()
        # Create a single quantum register for these qubits
        # subroutine += self._classical_register_command()
        subroutine += self._quantum_register_command()
        for command in self._pop_pending_commands():
            netqasm_command = self._get_netqasm_command(command)
            subroutine += netqasm_command

        indented_subroutine = '\n'.join(f"    {line}" for line in subroutine.split('\n'))
        self._logger.debug(f"Flushing subroutine:\n{indented_subroutine}")

        # Parse, assembly and possibly compile the subroutine
        subroutine = self._pre_process_subroutine(subroutine)

        # Commit the subroutine to the quantum device
        self.commit(subroutine, block=block)

        self._post_flush()

    def _post_flush(self):
        # Move to a new qubit register
        self._current_quantum_register_address = self._get_new_quantum_register_address()

    def _pop_pending_commands(self):
        pending_commands = self._pending_commands
        self._pending_commands = []
        return pending_commands

    def _pre_process_subroutine(self, subroutine):
        """Parses and assembles the subroutine.

        Can be subclassed and overried for more elaborate compiling.
        """
        parser = Parser(subroutine)
        subroutine = Subroutine(
            netqasm_version=parser.netqasm_version,
            app_id=parser.app_id,
            instructions=parser.instructions,
        )
        return subroutine

    # def _classical_register_command(self):
    #     address = self._get_classical_register_address()
    #     for index in self._used_classical_reg_indices:
    #         if not self._allocated_classical_reg_indices[index]:
    #             num_bits += 1
    #     num_bits = len(self._used_classical_reg_indices)
    #     if num_bits == 0:
    #         return ""
    #     instr_str = instruction_to_string(Instruction.CREG)

    #     for index in self._used_classical_reg_indices:
    #         self._allocated_classical_reg_indices[index] = True

    #     return f"{instr_str}({num_bits}) @{address}\n"

    def _quantum_register_command(self):
        # Check how many qubits are not allocated for the current address
        num_qubits = len(self._unallocated_qubit_indices)
        if num_qubits == 0:
            return ""
        self._unallocated_qubit_indices = []
        address = self._current_quantum_register_address
        instr_str = instruction_to_string(Instruction.QREG)

        return f"{instr_str}({num_qubits}) @{address}\n"

    def _get_new_quantum_register_address(self):
        for address in count(0):
            if address not in self._used_quantum_addresses:
                self._current_quantum_register_address = address
                return address

    def _get_shared_classical_register_address(self):
        # 'sm' is a keyword for the shared memory and has address 0
        return 'sm'

    @abc.abstractmethod
    def commit(self, msg):
        pass

    def _get_subroutine_preamble(self):
        return f"""# NETQASM {NETQASM_VERSION}
# APPID {self._appID}
"""

    def _get_netqasm_command(self, command):
        instr = _CQC_TO_NETQASM_INSTR[command.command]
        if command.command == CQC_CMD_MEASURE:
            c_address = self._current_classical_register_address
            q_address, q_index = command.qID
            c_index = command.kwargs['classical_reg_index']
            return f"{instr} @{q_address}[{q_index}] {c_address}[{c_index}]"
        else:
            address, index = command.qID
            return f"{instr} @{address}[{index}]\n"

    def _handle_factory_response(self, num_iter, response_amount, should_notify=False):
        raise NotImplementedError

    def get_remote_from_directory_or_address(self, name, **kwargs):
        raise NotImplementedError

    def _handle_epr_response(self, notify):
        raise NotImplementedError

    def readMessage(self):
        raise NotImplementedError

    def _get_new_quantum_reg_index(self):
        index = self._get_new_reg_index(tp="quantum")
        self._unallocated_qubit_indices.append(index)
        return index

    def _get_new_classical_reg_index(self):
        return self._get_new_reg_index(tp="classical")

    def _get_new_reg_index(self, tp):
        if tp == "quantum":
            address = self._current_quantum_register_address
            used_ids = self._used_quantum_reg_indices[address]
        elif tp == "classical":
            address = self._current_classical_register_address
            used_ids = self._used_classical_reg_indices[address]
        for virtual_id in count(0):
            if virtual_id not in used_ids:
                used_ids.append(virtual_id)
                return virtual_id
