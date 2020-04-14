import logging
import operator
from enum import Enum, auto
from types import GeneratorType
from collections import defaultdict
from itertools import count

from netqasm.subroutine import Command, Register, ArrayEntry, ArraySlice
from netqasm.instructions import Instruction, instruction_to_string
from netqasm.sdk.shared_memory import get_shared_memory, setup_registers, Arrays
from netqasm.network_stack import BaseNetworkStack


class OperandType(Enum):
    """Types of operands that a command can have"""
    QUBIT = auto()
    READ = auto()
    WRITE = auto()
    ADDRESS = auto()


def inc_program_counter(method):
    def new_method(self, subroutine_id, operands):
        output = method(self, subroutine_id, operands)
        if isinstance(output, GeneratorType):
            yield from output
        self._program_counters[subroutine_id] += 1
    return new_method


class Executioner:

    def __init__(self, name=None, num_qubits=5):
        """Executes a sequence of NetQASM instructions.

        The methods starting with `_instr_xxx` define what a given instruction should do and
        returns the new program counter (+1 unless a branching instruction).
        There are default implementations of these methods, however those involving qubits simply logs (DEBUG) what
        is being executed without actually updating any qubit state. For this reason the measurement instruction
        simply leaves the classical register unchanged.

        The intention is that all these methods should be overriden to define what should actually happen
        but the default implementations can be used testing and debugging.

        Parameters
        ----------
        name : str or None
            Give a name to the executioner for logging purposes.
        num_qubits : int
            The number of qubits for the executioner to use
        """

        if name is None:
            self._name = f"{self.__class__}"
        else:
            self._name = name

        self._instruction_handlers = self._get_instruction_handlers()

        # Registers for different apps
        self._registers = {}

        # Arrays stored in memory for different apps
        self._app_arrays = {}

        # Shared memory with host for different apps
        self._shared_memories = {}

        self._qubit_unit_modules = {}

        # There will be seperate program counters for each subroutine
        self._program_counters = defaultdict(int)

        # Keep track of what subroutines are currently handled
        self._subroutines = {}

        # Keep track of what physical qubit addresses are in use
        self._used_physical_qubit_addresses = []

        # Keep track of the last create epr request without a returned create ID
        self._last_create_epr_request = None

        # Keep track of the create epr requests in progress
        self._epr_create_requests = {}

        # Keep track of the recv epr requests in progress
        self._epr_recv_requests = defaultdict(list)

        # Network stack
        self._network_stack = None

        self._logger = logging.getLogger(f"{self.__class__.__name__}({self._name})")

    @property
    def network_stack(self):
        return self._network_stack

    @network_stack.setter
    def network_stack(self, network_stack):
        if not isinstance(network_stack, BaseNetworkStack):
            raise TypeError(f"network_stack must be an instance of BaseNetworkStack, not {type(network_stack)}")
        self._network_stack = network_stack

    def init_new_application(self, app_id, max_qubits):
        """Sets up a unit module and a shared memory for a new application"""
        self.allocate_new_qubit_unit_module(app_id=app_id, num_qubits=max_qubits)
        self.setup_registers(app_id=app_id)
        self.setup_arrays(app_id=app_id)
        self.new_shared_memory(app_id=app_id)

    def setup_registers(self, app_id):
        """Setup registers for application"""
        self._registers[app_id] = setup_registers()

    def setup_arrays(self, app_id):
        """Setup memory for storing arrays for application"""
        self._app_arrays[app_id] = Arrays()

    def new_shared_memory(self, app_id):
        """Instanciated a new shared memory with an application"""
        self._shared_memories[app_id] = get_shared_memory(node_name=self._name, key=app_id)

    def reset_program_counter(self, subroutine_id):
        """Resets the program counter for a given subroutine ID"""
        self._program_counters.pop(subroutine_id, 0)

    def clear_subroutine(self, subroutine_id):
        """Clears a subroutine from the executioner"""
        self.reset_program_counter()
        self._subroutines.pop(subroutine_id, 0)

    def _get_instruction_handlers(self):
        """Creates the dictionary of instruction handlers"""
        instruction_handlers = {
            instr: getattr(self, f"_instr_{instruction_to_string(instr)}") for instr in Instruction
        }
        return instruction_handlers

    def execute_subroutine(self, subroutine):
        """Executes the a subroutine given to the executioner"""
        subroutine_id = self._get_new_subroutine_id()
        self._subroutines[subroutine_id] = subroutine
        self.reset_program_counter(subroutine_id)
        output = self._execute_commands(subroutine_id, subroutine.commands)
        if isinstance(output, GeneratorType):
            yield from output

    def _get_new_subroutine_id(self):
        for subroutine_id in count(0):
            if subroutine_id not in self._subroutines:
                return subroutine_id

    def _execute_commands(self, subroutine_id, commands):
        """Executes a given subroutine"""
        while self._program_counters[subroutine_id] < len(commands):
            command = commands[self._program_counters[subroutine_id]]
            output = self._execute_command(subroutine_id, command)
            if isinstance(output, GeneratorType):
                yield from output

    def _execute_command(self, subroutine_id, command):
        """Executes a single instruction"""
        if not isinstance(command, Command):
            raise TypeError(f"Expected a Command, not {type(command)}")
        self._assert_number_args(command.args, num=0)
        output = self._instruction_handlers[command.instruction](subroutine_id, command.operands)
        if isinstance(output, GeneratorType):
            yield from output

    @inc_program_counter
    def _instr_set(self, subroutine_id, operands):
        register = operands[0]
        constant = operands[1]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._set_register(app_id, register, constant.value)

    def _set_register(self, app_id, register, value):
        self._registers[app_id][register.name][register.index] = value

    def _get_register(self, app_id, register):
        return self._registers[app_id][register.name][register.index]

    @inc_program_counter
    def _instr_qalloc(self, subroutine_id, operands):
        register = operands[0]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        qubit_address = self._get_register(app_id, register)
        self._allocate_physical_qubit(subroutine_id, qubit_address)
        self._logger.debug(f"Taking qubit at address {qubit_address}")

    @inc_program_counter
    def _instr_init(self, subroutine_id, operands):
        yield from self._handle_single_qubit_instr(Instruction.INIT, subroutine_id, operands)

    @inc_program_counter
    def _instr_store(self, subroutine_id, operands):
        register = operands[0]
        array_entry = operands[1]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        value = self._get_register(app_id, register)
        self._set_array_entry(app_id=app_id, array_entry=array_entry, value=value)
        self._logger.debug(f"Storing value {value} from register {register} to array entry {array_entry}")

    @inc_program_counter
    def _instr_load(self, subroutine_id, operands):
        register = operands[0]
        array_entry = operands[1]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        value = self._get_array_entry(app_id=app_id, array_entry=array_entry)
        value = self._set_register(app_id, register, value)
        self._logger.debug(f"Storing value {value} from array entry {array_entry} to register {register}")

    @inc_program_counter
    def _instr_lea(self, subroutine_id, operands):
        register = operands[0]
        address = operands[1]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._set_register(app_id=app_id, register=register, value=address.address)
        self._logger.debug(f"Storing address of {address} to register {register}")

    @inc_program_counter
    def _instr_undef(self, subroutine_id, operands):
        array_entry = operands[0]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._set_array_entry(app_id=app_id, array_entry=array_entry, value=None)
        self._logger.debug(f"Unset array entry {array_entry}")

    @inc_program_counter
    def _instr_array(self, subroutine_id, operands):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        length = self._get_register(app_id, operands[0])
        address = operands[1]
        self._initialize_array(app_id=app_id, address=address, length=length)
        self._logger.debug(f"Initializing an array of length {length} at address {address}")

    def _initialize_array(self, app_id, address, length):
        arrays = self._app_arrays[app_id]
        arrays.init_new_array(address, length)

    def _instr_jmp(self, subroutine_id, operands):
        self._handle_branch_instr(
            instr=Instruction.JMP,
            subroutine_id=subroutine_id,
            operands=operands,
        )

    def _instr_bez(self, subroutine_id, operands):
        self._handle_branch_instr(
            instr=Instruction.BEZ,
            subroutine_id=subroutine_id,
            operands=operands,
        )

    def _instr_bnz(self, subroutine_id, operands):
        self._handle_branch_instr(
            instr=Instruction.BNZ,
            subroutine_id=subroutine_id,
            operands=operands,
        )

    def _instr_beq(self, subroutine_id, operands):
        self._handle_branch_instr(
            instr=Instruction.BEQ,
            subroutine_id=subroutine_id,
            operands=operands,
        )

    def _instr_bne(self, subroutine_id, operands):
        self._handle_branch_instr(
            instr=Instruction.BNE,
            subroutine_id=subroutine_id,
            operands=operands,
        )

    def _instr_blt(self, subroutine_id, operands):
        self._handle_branch_instr(
            instr=Instruction.BLT,
            subroutine_id=subroutine_id,
            operands=operands,
        )

    def _instr_bge(self, subroutine_id, operands):
        self._handle_branch_instr(
            instr=Instruction.BGE,
            subroutine_id=subroutine_id,
            operands=operands,
        )

    def _handle_branch_instr(self, instr, subroutine_id, operands):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        a, b = None, None
        if instr != Instruction.JMP:
            a = self._get_register(app_id=app_id, register=operands[0])
        if instr in [Instruction.BEQ, Instruction.BNE, Instruction.BLT, Instruction.BGE]:
            b = self._get_register(app_id=app_id, register=operands[1])

        condition_func = {
            Instruction.JMP: lambda a, b: True,
            Instruction.BEZ: lambda a, b: operator.eq(a, 0),
            Instruction.BNZ: lambda a, b: operator.ne(a, 0),
            Instruction.BEQ: operator.eq,
            Instruction.BNE: operator.ne,
            Instruction.BLT: operator.lt,
            Instruction.BGE: operator.ge,
        }[instr]

        if condition_func(a, b):
            jump_address = operands[-1].value
            self._logger.debug(f"Branching to line {jump_address}, since {instr}(a={a}, b={b}) "
                               f"is True, with values from registers {operands[:-1]}")
            self._program_counters[subroutine_id] = jump_address
        else:
            self._logger.debug(f"Don't branch, since {instr}(a={a}, b={b}) "
                               f"is False, with values from registers {operands[:-1]}")
            self._program_counters[subroutine_id] += 1

    @inc_program_counter
    def _instr_add(self, subroutine_id, operands):
        self._handle_binary_classical_instr(Instruction.ADD, subroutine_id, operands)

    @inc_program_counter
    def _instr_addm(self, subroutine_id, operands):
        self._handle_binary_classical_instr(Instruction.ADDM, subroutine_id, operands)

    @inc_program_counter
    def _instr_sub(self, subroutine_id, operands):
        self._handle_binary_classical_instr(Instruction.SUB, subroutine_id, operands)

    @inc_program_counter
    def _instr_subm(self, subroutine_id, operands):
        self._handle_binary_classical_instr(Instruction.SUBM, subroutine_id, operands)

    @inc_program_counter
    def _instr_x(self, subroutine_id, operands):
        yield from self._handle_single_qubit_instr(Instruction.X, subroutine_id, operands)

    @inc_program_counter
    def _instr_y(self, subroutine_id, operands):
        yield from self._handle_single_qubit_instr(Instruction.Y, subroutine_id, operands)

    @inc_program_counter
    def _instr_z(self, subroutine_id, operands):
        yield from self._handle_single_qubit_instr(Instruction.Z, subroutine_id, operands)

    @inc_program_counter
    def _instr_h(self, subroutine_id, operands):
        yield from self._handle_single_qubit_instr(Instruction.H, subroutine_id, operands)

    @inc_program_counter
    def _instr_k(self, subroutine_id, operands):
        yield from self._handle_single_qubit_instr(Instruction.K, subroutine_id, operands)

    @inc_program_counter
    def _instr_t(self, subroutine_id, operands):
        yield from self._handle_single_qubit_instr(Instruction.T, subroutine_id, operands)

    @inc_program_counter
    def _instr_rot_x(self, subroutine_id, operands):
        yield from self._handle_single_qubit_instr(Instruction.ROT_X, subroutine_id, operands)

    @inc_program_counter
    def _instr_rot_y(self, subroutine_id, operands):
        yield from self._handle_single_qubit_instr(Instruction.ROT_Y, subroutine_id, operands)

    @inc_program_counter
    def _instr_rot_z(self, subroutine_id, operands):
        yield from self._handle_single_qubit_instr(Instruction.ROT_Z, subroutine_id, operands)

    @inc_program_counter
    def _instr_cnot(self, subroutine_id, operands):
        yield from self._handle_two_qubit_instr(Instruction.CNOT, subroutine_id, operands)

    @inc_program_counter
    def _instr_cphase(self, subroutine_id, operands):
        yield from self._handle_two_qubit_instr(Instruction.CPHASE, subroutine_id, operands)

    @inc_program_counter
    def _instr_meas(self, subroutine_id, operands):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address = self._get_register(app_id=app_id, register=operands[0])
        self._logger.debug(f"Measuring the qubit at address {q_address}, "
                           f"placing the outcome in register {operands[1]}")
        outcome = self._do_meas(subroutine_id=subroutine_id, q_address=q_address)
        self._set_register(app_id=app_id, register=operands[1], value=outcome)

    def _do_meas(self, subroutine_id, q_address):
        """Performs a measurement on a single qubit"""
        # Always give outcome zero in the default debug class
        return 0

    @inc_program_counter
    def _instr_create_epr(self, subroutine_id, operands):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        remote_node_id = self._get_register(app_id=app_id, register=operands[0])
        purpose_id = self._get_register(app_id=app_id, register=operands[1])
        q_array_address = self._get_register(app_id=app_id, register=operands[2])
        arg_array_address = self._get_register(app_id=app_id, register=operands[3])
        ent_info_array_address = self._get_register(app_id=app_id, register=operands[4])
        self._logger.debug(f"Creating EPR pair with remote node id {remote_node_id} and purpose_id {purpose_id}"
                           f"using qubit addresses stored in array with address {q_array_address}, "
                           f"using arguments stored in array with address {arg_array_address}, "
                           f"placing the entanglement information in array at address {ent_info_array_address}")
        self._do_create_epr(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            q_array_address=q_array_address,
            arg_array_address=arg_array_address,
            ent_info_array_address=ent_info_array_address,
        )

    def _do_create_epr(
        self,
        subroutine_id,
        remote_node_id,
        purpose_id,
        q_array_address,
        arg_array_address,
        ent_info_array_address,
    ):
        pass

    @inc_program_counter
    def _instr_recv_epr(self, subroutine_id, operands):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        remote_node_id = self._get_register(app_id=app_id, register=operands[0])
        purpose_id = self._get_register(app_id=app_id, register=operands[1])
        q_array_address = self._get_register(app_id=app_id, register=operands[2])
        ent_info_array_address = self._get_register(app_id=app_id, register=operands[3])
        self._logger.debug(f"Receiving EPR pair with remote node id {remote_node_id} and purpose_id {purpose_id}"
                           f"using qubit addresses stored in array with address {q_array_address}, "
                           f"placing the entanglement information in array at address {ent_info_array_address}")
        self._do_recv_epr(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            q_array_address=q_array_address,
            ent_info_array_address=ent_info_array_address,
        )

    def _do_recv_epr(self, subroutine_id, remote_node_id, purpose_id, q_array_address, ent_info_array_address):
        pass

    @inc_program_counter
    def _instr_wait_all(self, subroutine_id, operands):
        array_slice = operands[0]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._logger.debug(f"Waiting for all entries in array slice {array_slice} to become defined")
        while True:
            values = self._get_array_slice(app_id=app_id, array_slice=array_slice)
            if all(value is not None for value in values):
                output = self._do_wait()
                if isinstance(output, GeneratorType):
                    yield from output
            else:
                break
        self._logger.debug(f"Finished waiting")

    @inc_program_counter
    def _instr_wait_any(self, subroutine_id, operands):
        array_slice = operands[0]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        self._logger.debug(f"Waiting for any entry in array slice {array_slice} to become defined")
        while True:
            values = self._get_array_slice(app_id=app_id, array_slice=array_slice)
            if any(value is not None for value in values):
                output = self._do_wait()
                if isinstance(output, GeneratorType):
                    yield from output
            else:
                break
        self._logger.debug(f"Finished waiting")

    @inc_program_counter
    def _instr_wait_single(self, subroutine_id, operands):
        array_entry = operands[0]
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
        self._logger.debug(f"Finished waiting")

    def _do_wait(self):
        pass

    @inc_program_counter
    def _instr_qfree(self, subroutine_id, operands):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address = self._get_register(app_id=app_id, register=operands[0])

        self._free_physical_qubit(subroutine_id, q_address)
        self._logger.debug(f"Freeing qubit at address {q_address}")

    @inc_program_counter
    def _instr_ret_reg(self, subroutine_id, operands):
        register = operands[0]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        value = self._get_register(app_id=app_id, register=register)
        self._update_shared_memory(register, value)

    @inc_program_counter
    def _instr_ret_arr(self, subroutine_id, operands):
        array_slice = operands[0]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        value = self._get_array_slice(app_id=app_id, array_slice=array_slice)
        self._update_shared_memory(array_slice, value)

    def _update_shared_memory(self, app_id, entry, value):
        shared_memory = self._shared_memories[app_id]
        if isinstance(entry, Register):
            shared_memory.set_register(entry, value)
        elif isinstance(entry, ArrayEntry):
            shared_memory.set_array_entry(entry, value)
        elif isinstance(entry, ArraySlice):
            shared_memory.set_array_entry(entry, value)
        else:
            raise TypeError(f"Cannot update shared memory with entry specified as {entry}")

    def _get_unit_module(self, subroutine_id):
        app_id = self._get_app_id(subroutine_id)
        unit_module = self._qubit_unit_modules.get(app_id)
        if unit_module is None:
            raise RuntimeError(f"Application with app ID {app_id} has not allocated qubit unit module")
        return unit_module

    def _get_position_in_unit_module(self, subroutine_id, address):
        unit_module = self._get_unit_module(subroutine_id)
        if address >= len(unit_module):
            raise IndexError(f"The address {address} is not within the allocated unit module "
                             f"of size {len(unit_module)}")
        position = unit_module[address]
        if position is None:
            app_id = self._get_app_id(subroutine_id)
            raise RuntimeError(f"The qubit with address {address} was not allocated for app ID {app_id}")
        return position

    def _get_array_entry(self, app_id, array_entry):
        return self._app_arrays[app_id][array_entry.address, array_entry.index]

    def _set_array_entry(self, app_id, array_entry, value):
        self._app_arrays[app_id][array_entry.address, array_entry.index] = value

    def _get_array_slice(self, app_id, array_slice):
        return self._app_arrays[app_id][array_slice.address, array_slice.start:array_slice.stop]

    def allocate_new_qubit_unit_module(self, app_id, num_qubits):
        unit_module = self._get_new_qubit_unit_module(num_qubits)
        self._qubit_unit_modules[app_id] = unit_module

    def _get_new_qubit_unit_module(self, num_qubits):
        return [None] * num_qubits

    def _allocate_physical_qubit(self, subroutine_id, address):
        unit_module = self._get_unit_module(subroutine_id)
        if unit_module[address] is None:
            unit_module[address] = self._get_unused_physical_qubit(address)
        else:
            app_id = self._subroutines[subroutine_id].app_id
            raise RuntimeError(f"QubitAddress at address {address} for application {app_id} is already allocated")

    def _free_physical_qubit(self, subroutine_id, address):
        unit_module = self._get_unit_module(subroutine_id)
        if unit_module[address] is None:
            app_id = self._subroutines[subroutine_id].app_id
            raise RuntimeError(f"QubitAddress at address {address} for application {app_id} is not allocated "
                               "and cannot be freed")
        else:
            unit_module[address] = None
            self._used_physical_qubit_addresses.remove(address)

    def _get_unused_physical_qubit(self, address):
        # Assuming that the topology of the unit module is a complete graph
        # is does not matter which unused physical qubit we choose for now
        for physical_address in count(0):
            if physical_address not in self._used_physical_qubit_addresses:
                self._used_physical_qubit_addresses.append(physical_address)
                return physical_address

    def _handle_single_qubit_instr(self, instr, subroutine_id, operands):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address = self._get_register(app_id=app_id, register=operands[0])
        self._logger.debug(f"Performing {instr} on the qubit at address {q_address}")
        output = self._do_single_qubit_instr(instr, subroutine_id, q_address)
        if isinstance(output, GeneratorType):
            yield from output

    def _do_single_qubit_instr(self, instr, subroutine_id, address):
        """Performs a single qubit gate"""
        pass

    def _handle_two_qubit_instr(self, instr, subroutine_id, operands):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address1 = self._get_register(app_id=app_id, register=operands[0])
        q_address2 = self._get_register(app_id=app_id, register=operands[1])
        self._logger.debug(f"Performing {instr} on the qubits at addresses {q_address1} and {q_address2}")
        output = self._do_two_qubit_instr(instr, subroutine_id, q_address1, q_address2)
        if isinstance(output, GeneratorType):
            yield from output

    def _do_two_qubit_instr(self, instr, subroutine_id, address1, address2):
        """Performs a two qubit gate"""
        pass

    def _handle_binary_classical_instr(self, instr, subroutine_id, operands):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        if instr in [Instruction.ADDM, Instruction.SUBM]:
            mod = self._get_register(app_id=app_id, register=operands[3])
        else:
            mod = None
        if mod is not None and mod < 1:
            raise RuntimeError("Modulus needs to be greater or equal to 1, not {mod}")
        a = self._get_register(app_id=app_id, register=operands[1])
        b = self._get_register(app_id=app_id, register=operands[2])
        value = self._compute_binary_classical_instr(instr, a, b, mod=mod)
        self._set_register(app_id=app_id, register=operands[0], value=value)
        self._logger.debug(f"Performing {instr} of a={a} and b={b} (mod {mod})"
                           f"and storing the value at address {operands[0]}")

    def _compute_binary_classical_instr(self, instr, a, b, mod=1):
        op = {
            Instruction.ADD: operator.add,
            Instruction.SUB: operator.sub,
        }[instr]
        if mod is None:
            return op(a, b)
        else:
            return op(a, b) % mod

    def _assert_number_args(self, args, num):
        if not len(args) == num:
            raise TypeError(f"Expected {num} arguments, got {len(args)}")

    def _get_app_id(self, subroutine_id):
        """Returns the app ID for the given subroutine"""
        subroutine = self._subroutines.get(subroutine_id)
        if subroutine is None:
            raise ValueError(f"Unknown subroutine with ID {subroutine_id}")
        return subroutine.app_id
