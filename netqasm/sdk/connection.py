import abc
import logging
from itertools import count
from collections import namedtuple

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
from netqasm.parser import Parser
from netqasm.encoder import Instruction, instruction_to_string
from netqasm.string_util import is_number
from netqasm.sdk.shared_memory import get_shared_memory


_Command = namedtuple("Command", ["qID", "command", "kwargs"])


_CQC_TO_NETQASM_INSTR = {
    CQC_CMD_NEW: instruction_to_string(Instruction.INIT),
    CQC_CMD_X: instruction_to_string(Instruction.X),
    CQC_CMD_H: instruction_to_string(Instruction.H),
    CQC_CMD_MEASURE: instruction_to_string(Instruction.MEAS),
    CQC_CMD_RELEASE: instruction_to_string(Instruction.QFREE),
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

    def close(self, release_qubits=True, release_bits=True):
        super().close(release_qubits=release_qubits)

    def new_qubitID(self):
        return self._get_new_qubit_address()

    def _handle_create_qubits(self, num_qubits):
        raise NotImplementedError

    def return_meas_outcome(self):
        raise NotImplementedError

    def _init_new_app(self, max_qubits):
        """Informs the backend of the new application and how many qubits it will maximally use"""
        pass

    def put_command(self, qID, command, **kwargs):
        self._logger.debug(f"Put new command={command_to_string(command)} for qubit qID={qID} with kwargs={kwargs}")
        self._pending_commands.append(_Command(qID=qID, command=command, kwargs=kwargs))

    def flush(self, block=True):
        subroutine = self._pop_pending_subroutine()
        if subroutine is None:
            return

        preamble = self._get_subroutine_preamble()
        subroutine = preamble + subroutine

        self._commit_subroutine(subroutine=subroutine, block=block)

    def _commit_subroutine(self, subroutine, block=True):
        # For logging
        print(subroutine)
        indented_subroutine = '\n'.join(f"    {line}" for line in subroutine.split('\n'))
        self._logger.debug(f"Flushing subroutine:\n{indented_subroutine}")

        # Parse, assembly and possibly compile the subroutine
        subroutine = self._pre_process_subroutine(subroutine)

        # Commit the subroutine to the quantum device
        self.commit(subroutine, block=block)

    def _put_subroutine(self, subroutine):
        """Stores a subroutine to be flushed"""
        self._pending_subroutine = subroutine

    def _subroutine_from_commands(self, commands):
        # Build sub-routine
        subroutine = ""
        for command in commands:
            netqasm_command = self._get_netqasm_command(command)
            subroutine += netqasm_command
        return subroutine

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

    def _pop_pending_commands(self):
        commands = self._pending_commands
        self._pending_commands = []
        return commands

    def _pre_process_subroutine(self, subroutine):
        """Parses and assembles the subroutine.

        Can be subclassed and overried for more elaborate compiling.
        """
        return Parser(subroutine).subroutine

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
            c_address = command.kwargs['outcome_address']
            if isinstance(c_address, int) or is_number(c_address):
                c_address = Parser.ADDRESS_START + str(c_address)
            q_address = command.qID
            meas = f"{instr} {Parser.ADDRESS_START}{q_address} {c_address}\n"
            qfree = f"qfree {Parser.ADDRESS_START}{q_address}\n"
            return meas + qfree
        if command.command == CQC_CMD_NEW:
            address = command.qID
            qtake = f"qtake {Parser.ADDRESS_START}{address}\n"
            init = f"init {Parser.ADDRESS_START}{address}\n"
            return qtake + init
        else:
            address = command.qID
            return f"{instr} {Parser.ADDRESS_START}{address}\n"

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
        body(self)
        body_subroutine = self._pop_pending_subroutine()
        current_branch_variables = Parser._find_current_branch_variables(body_subroutine)
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
