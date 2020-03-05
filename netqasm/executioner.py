import logging
from enum import Enum, auto
from types import GeneratorType
from collections import defaultdict
from dataclasses import dataclass
from itertools import count

from netsquid_magic.link_layer import LinkLayerCreate, LinkLayerRecv, ReturnType, RequestType, get_creator_node_id

from netqasm.parser import Command, QubitAddress, Address, Array, AddressMode
from netqasm.encoder import Instruction, string_to_instruction
from netqasm.sdk.shared_memory import get_shared_memory
from netqasm.network_stack import BaseNetworkStack


class OperandType(Enum):
    """Types of operands that a command can have"""
    QUBIT = auto()
    READ = auto()
    WRITE = auto()
    ADDRESS = auto()


def inc_program_counter(method):
    def new_method(self, subroutine_id, args, operands):
        output = method(self, subroutine_id, args, operands)
        if isinstance(output, GeneratorType):
            yield from output
        self._program_counters[subroutine_id] += 1
    return new_method


@dataclass
class CreateData:
    subroutine_id: int
    ent_info_address: int
    create_request: LinkLayerCreate
    pairs_left: int


@dataclass
class RecvData:
    subroutine_id: int
    ent_info_address: int
    recv_request: LinkLayerRecv
    pairs_left: int


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

        self._epr_response_handlers = self._get_epr_response_handlers()

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
        self.new_shared_memory(app_id=app_id)

    def new_shared_memory(self, app_id):
        """Instanciated a new shared memory with an application"""
        self._shared_memories[app_id] = self._get_shared_memory(app_id=app_id)

    def _get_shared_memory(self, app_id):
        return get_shared_memory(node_name=self._name, key=app_id)

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
            Instruction.QALLOC: self._instr_qalloc,
            Instruction.INIT: self._instr_init,
            Instruction.STORE: self._instr_store,
            Instruction.ARRAY: self._instr_array,
            Instruction.ADD: self._instr_add,
            Instruction.H: self._instr_h,
            Instruction.X: self._instr_x,
            Instruction.CNOT: self._instr_cnot,
            Instruction.MEAS: self._instr_meas,
            Instruction.CREATE_EPR: self._instr_create_epr,
            Instruction.RECV_EPR: self._instr_recv_epr,
            Instruction.BEQ: self._instr_beq,
            Instruction.WAIT: self._instr_wait,
            Instruction.QFREE: self._instr_qfree,
        }
        return instruction_handlers

    def _get_epr_response_handlers(self):
        epr_response_handlers = {
            # ReturnType.CREATE_ID: self._handle_epr_create_id_response,
            ReturnType.ERR: self._handle_epr_err_response,
            ReturnType.OK_K: self._handle_epr_ok_k_response,
            ReturnType.OK_M: self._handle_epr_ok_m_response,
            ReturnType.OK_R: self._handle_epr_ok_r_response,
        }

        return epr_response_handlers

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
        instr = string_to_instruction(command.instruction)
        output = self._instruction_handlers[instr](subroutine_id, command.args, command.operands)
        if isinstance(output, GeneratorType):
            yield from output

    @inc_program_counter
    def _instr_qalloc(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1, operand_types=OperandType.QUBIT)
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        address = self._get_address_value(app_id=app_id, operand=operands[0])
        self._allocate_physical_qubit(subroutine_id, address)
        self._logger.debug(f"Taking qubit at address {address}")

    @inc_program_counter
    def _instr_init(self, subroutine_id, args, operands):
        yield from self._handle_single_qubit_instr(Instruction.INIT, subroutine_id, args, operands)

    @inc_program_counter
    def _instr_store(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=2, operand_types=[OperandType.WRITE, OperandType.READ])
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        value = self._get_address_value(app_id=app_id, operand=operands[1])
        self._set_address_value(app_id=app_id, operand=operands[0], value=value)
        self._logger.debug(f"Storing value {value} at address given by operand {operands[0]}")

    @inc_program_counter
    def _instr_array(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=1)
        length = args[0]
        self._assert_operands(operands, num=1, operand_types=OperandType.ADDRESS)
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        address = self._get_address(app_id=app_id, operand=operands[0])
        self._initialize_array(app_id=app_id, address=address, length=length)
        self._logger.debug(f"Initializing an array of length {length} at address {address}")

    def _initialize_array(self, app_id, address, length):
        shared_memory = self._shared_memories[app_id]
        current = shared_memory[address]
        if current is not None:
            raise ValueError(f"Address {address} for app with ID {app_id} is already initialized")
        shared_memory[address] = [None] * length

    @inc_program_counter
    def _instr_add(self, subroutine_id, args, operands):
        self._handle_binary_classical_instr(Instruction.ADD, subroutine_id, args, operands)

    @inc_program_counter
    def _instr_h(self, subroutine_id, args, operands):
        yield from self._handle_single_qubit_instr(Instruction.H, subroutine_id, args, operands)

    @inc_program_counter
    def _instr_x(self, subroutine_id, args, operands):
        yield from self._handle_single_qubit_instr(Instruction.X, subroutine_id, args, operands)

    @inc_program_counter
    def _instr_cnot(self, subroutine_id, args, operands):
        yield from self._handle_two_qubit_instr(Instruction.CNOT, subroutine_id, args, operands)

    @inc_program_counter
    def _instr_meas(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=2, operand_types=[OperandType.QUBIT, OperandType.WRITE])
        self._logger.debug(f"Measuring the qubit at address {operands[0]}, "
                           f"placing the outcome at address {operands[1]}")
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        q_address = self._get_address_value(app_id=app_id, operand=operands[0])
        self._do_meas(subroutine_id=subroutine_id, q_address=q_address, c_operand=operands[1])

    def _do_meas(self, subroutine_id, q_address, c_operand):
        """Performs a measurement on a single qubit"""
        # Always give outcome zero in the default debug class
        outcome = 0
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        try:
            self._set_address_value(app_id=app_id, operand=c_operand, value=outcome)
        except IndexError:
            logging.warning("Measurement outcome dropped since no more entries in classical register")

    @inc_program_counter
    def _instr_create_epr(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=2)
        remote_node_id = args[0]
        purpose_id = args[1]
        self._assert_operands(operands, num=3, operand_types=OperandType.ADDRESS)
        self._logger.debug(f"Creating EPR pair using qubit addresses stored at {operands[0]}, "
                           f"using arguments stored at {operands[1]}, "
                           f"placing the entanglement information at address to be stored at {operands[2]}")
        self._do_create_epr(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            q_address=operands[0].address,
            arg_address=operands[1].address,
            ent_info_address=operands[2].address,
        )

    def _do_create_epr(self, subroutine_id, remote_node_id, purpose_id, q_address, arg_address, ent_info_address):
        if self.network_stack is None:
            raise RuntimeError("SubroutineHandler has not network stack")
        create_request = self._get_create_request(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            arg_address=arg_address,
        )
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        num_qubits = len(self._shared_memories[app_id][q_address])
        assert num_qubits == create_request.number, "Not enough qubit addresses"
        create_id = self.network_stack.put(remote_node_id=remote_node_id, request=create_request)
        self._epr_create_requests[create_id] = CreateData(
            subroutine_id=subroutine_id,
            ent_info_address=ent_info_address,
            create_request=create_request,
            pairs_left=create_request.number,
        )

    def _get_create_request(self, subroutine_id, remote_node_id, purpose_id, arg_address):
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        args = self._shared_memories[app_id][arg_address]
        # NOTE remote_node_id and purpose_id comes as direct arguments
        args = [remote_node_id, purpose_id] + args

        # Use defaults if not specified
        expected_num_args = len(LinkLayerCreate._fields)
        if len(args) != expected_num_args:
            raise ValueError(f"Expected {expected_num_args} arguments, but got {len(args)}")
        kwargs = {}
        for arg, field, default in zip(args, LinkLayerCreate._fields, LinkLayerCreate.__new__.__defaults__):
            if arg is None:
                kwargs[field] = default
            else:
                kwargs[field] = arg
        kwargs["type"] = RequestType(kwargs["type"])

        return LinkLayerCreate(**kwargs)

    @inc_program_counter
    def _instr_recv_epr(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=2)
        remote_node_id = args[0]
        purpose_id = args[1]
        self._assert_operands(operands, num=2, operand_types=OperandType.ADDRESS)
        self._logger.debug(f"Receive EPR pair using qubit addresses stored at {operands[0]}, "
                           f"placing the entanglement information at address to be stored at {operands[1]}")
        self._do_recv_epr(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
            q_address=operands[0].address,
            ent_info_address=operands[1].address,
        )

    def _do_recv_epr(self, subroutine_id, remote_node_id, purpose_id, q_address, ent_info_address):
        if self.network_stack is None:
            raise RuntimeError("SubroutineHandler has not network stack")
        recv_request = self._get_recv_request(
            subroutine_id=subroutine_id,
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
        )
        # Check number of qubit addresses
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        num_qubits = len(self._shared_memories[app_id][q_address])
        self._epr_recv_requests[purpose_id].append(RecvData(
            subroutine_id=subroutine_id,
            ent_info_address=ent_info_address,
            recv_request=recv_request,
            pairs_left=num_qubits,
        ))
        self.network_stack.put(remote_node_id=remote_node_id, request=recv_request)

    def _get_recv_request(self, subroutine_id, remote_node_id, purpose_id):
        return LinkLayerRecv(
            remote_node_id=remote_node_id,
            purpose_id=purpose_id,
        )

    def _handle_epr_response(self, response):
        self._epr_response_handlers[response.type](response)

    def _handle_epr_err_response(self, response):
        raise RuntimeError(f"Got the following error from the network stack: {response}")

    def _handle_epr_ok_k_response(self, response):
        # NOTE this will probably be handled differently in an actual implementation
        # but is done in a simple way for now to allow for simulation
        # TODO cleanup this part
        creator_node_id = get_creator_node_id(self._node.ID, response)
        if creator_node_id == self._node.ID:
            create_id = response.create_id
            create_data = self._epr_create_requests[create_id]
            create_data.pairs_left -= 1
            if create_data.pairs_left == 0:
                self._epr_create_requests.pop(create_id)
            subroutine_id = create_data.subroutine_id
            ent_info_address = create_data.ent_info_address
        else:
            purpose_id = response.purpose_id
            recv_data = self._epr_recv_requests[purpose_id][0]
            recv_data.pairs_left -= 1
            if recv_data.pairs_left == 0:
                self._epr_recv_requests[purpose_id].pop(0)
            subroutine_id = recv_data.subroutine_id
            ent_info_address = recv_data.ent_info_address
        q_address = response.logical_qubit_id
        self._allocate_physical_qubit(subroutine_id, q_address)
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        full_ent_info_address = self._get_address(
            app_id=app_id,
            operand=Array(
                address=Address(address=ent_info_address, mode=AddressMode.DIRECT),
                index=None,
            ),
        )
        ent_info = [entry.value if isinstance(entry, Enum) else entry for entry in response]
        self._shared_memories[app_id][full_ent_info_address] = ent_info

    def _handle_epr_ok_m_response(self, response):
        raise NotImplementedError

    def _handle_epr_ok_r_response(self, response):
        raise NotImplementedError

    def _instr_beq(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=3, operand_types=OperandType.READ)
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        a = self._get_address_value(app_id=app_id, operand=operands[0])
        b = self._get_address_value(app_id=app_id, operand=operands[1])
        jump_address = self._get_address_value(app_id=app_id, operand=operands[2])
        if a == b:
            self._logger.debug(f"Branching to line {jump_address} since {a} = {b} "
                               f"from address {operands[0]} and {operands[1]}")
            self._program_counters[subroutine_id] = jump_address
        else:
            self._logger.debug(f"Don't branch, since {a} =! {b} "
                               f"from address {operands[0]} and {operands[1]}")
            self._program_counters[subroutine_id] += 1

    @inc_program_counter
    def _instr_wait(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1, operand_types=OperandType.READ)
        operand = operands[0]
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        if isinstance(operand, Address) and operand.mode == AddressMode.IMMEDIATE:
            num_wait = operand.address
            self._logger.debug(f"Waiting {num_wait} times")
            for _ in range(num_wait):
                output = self._do_wait()
                if isinstance(output, GeneratorType):
                    yield from output
        else:
            self._logger.debug(f"Waiting for address {operands[0]} to become defined")
            while True:
                value = self._get_address_value(app_id=app_id, operand=operands[0], assert_int=False)
                is_defined = True
                if value is None:
                    is_defined = False
                if isinstance(value, list):
                    if None in value:
                        is_defined = False
                if not is_defined:
                    output = self._do_wait()
                    if isinstance(output, GeneratorType):
                        yield from output
                else:
                    break
        self._logger.debug(f"Finished waiting")

    def _do_wait(self):
        pass

    @inc_program_counter
    def _instr_qfree(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1, operand_types=OperandType.QUBIT)
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        address = self._get_address_value(app_id=app_id, operand=operands[0])

        self._free_physical_qubit(subroutine_id, address)
        self._logger.debug(f"Freeing qubit at address {address}")

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

    def _get_address_value(self, app_id, operand, assert_int=True):
        if isinstance(operand, QubitAddress):
            return operand.address
        if isinstance(operand, Address) and operand.mode == AddressMode.IMMEDIATE:
            return operand.address
        else:
            address = self._get_address(app_id=app_id, operand=operand)
            shared_memory = self._shared_memories[app_id]
            value = shared_memory[address]
            if assert_int:
                if not isinstance(value, int):
                    raise TypeError(f"Expected an int at address {address}, but got {value}")
            return value

    def _get_unused_entry_of_array(self, app_id, array_address):
        shared_memory = self._shared_memories[app_id]
        array = shared_memory[array_address]
        if not isinstance(array, list):
            raise TypeError(f"Expected a list at address {array_address}, but got {array}")
        if array is None:
            raise ValueError(f"No array initialized at address {array_address} for app with ID {app_id}")
        for index, entry in enumerate(array):
            if entry is None:
                return index
        return None

    def _get_address(self, app_id, operand):
        if isinstance(operand, Array):
            array_address = operand.address.address
            if operand.index is None:
                index = self._get_unused_entry_of_array(app_id=app_id, array_address=array_address)
                if index is None:
                    raise RuntimeError(f"No unused index in the array at address {array_address} "
                                       f"for app with ID {app_id}")
            else:
                index = self._get_address_value(app_id=app_id, operand=operand.index)
            array_entry_address = array_address, index
            if operand.address.mode == AddressMode.DIRECT:
                return array_entry_address
            elif operand.address.mode == AddressMode.INDIRECT:
                shared_memory = self._shared_memories[app_id]
                indirect_address = shared_memory[array_entry_address]
                if not isinstance(indirect_address, int):
                    raise TypeError(f"Expected an int at address {array_entry_address}, not {indirect_address}")
                return indirect_address
        if operand.mode == AddressMode.IMMEDIATE:
            raise ValueError("Not an address mode")
        elif operand.mode == AddressMode.DIRECT:
            return operand.address
        elif operand.mode == AddressMode.INDIRECT:
            # AddressMode.INDIRECT
            address = operand.address
            shared_memory = self._shared_memories[app_id]
            indirect_address = shared_memory[address]
            if not isinstance(indirect_address, int):
                raise TypeError(f"Expected an int at address {address}, not {indirect_address}")
            return indirect_address
        else:
            raise TypeError(f"Unknown address mode {operand.mode}")

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

    def _handle_single_qubit_instr(self, instr, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1, operand_types=OperandType.QUBIT)
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        address = self._get_address_value(app_id=app_id, operand=operands[0])
        self._logger.debug(f"Performing {instr} on the qubit at address {address}")
        output = self._do_single_qubit_instr(instr, subroutine_id, address)
        if isinstance(output, GeneratorType):
            yield from output

    def _do_single_qubit_instr(self, instr, subroutine_id, address):
        """Performs a single qubit gate"""
        pass

    def _handle_two_qubit_instr(self, instr, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=2, operand_types=OperandType.QUBIT)
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        address1 = self._get_address_value(app_id=app_id, operand=operands[0])
        address2 = self._get_address_value(app_id=app_id, operand=operands[1])
        self._logger.debug(f"Performing {instr} on the qubits at addresses {address1} and {address2}")
        output = self._do_two_qubit_instr(instr, subroutine_id, address1, address2)
        if isinstance(output, GeneratorType):
            yield from output

    def _do_two_qubit_instr(self, instr, subroutine_id, address1, address2):
        """Performs a two qubit gate"""
        pass

    def _handle_binary_classical_instr(self, instr, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=3, operand_types=[OperandType.WRITE, OperandType.READ, OperandType.READ])
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        a = self._get_address_value(app_id=app_id, operand=operands[1])
        b = self._get_address_value(app_id=app_id, operand=operands[2])
        value = self._compute_binary_classical_instr(instr, a, b)
        self._set_address_value(app_id=app_id, operand=operands[0], value=value)
        self._logger.debug(f"Performing {instr} of a={a} and b={b} "
                           f"and storing the value at address {operands[0]}")

    def _compute_binary_classical_instr(self, instr, a, b):
        if instr == Instruction.ADD:
            return a + b
        else:
            raise RuntimeError("Unknown binary classical instructions {instr}")

    def _set_address_value(self, app_id, operand, value):
        address = self._get_address(app_id=app_id, operand=operand)
        shared_memory = self._shared_memories[app_id]
        shared_memory[address] = value

    def _assert_number_args(self, args, num):
        if not len(args) == num:
            raise TypeError(f"Expected {num} arguments, got {len(args)}")

    def _assert_operands(self, operands, num, operand_types):
        if isinstance(operand_types, OperandType):
            operand_types = [operand_types] * num
        if not len(operands) == num:
            raise TypeError(f"Expected {num} operands, got {len(operands)}")
        for operand, operand_type in zip(operands, operand_types):
            self._assert_operand(operand=operand, operand_type=operand_type)

    def _assert_operand(self, operand, operand_type):
        if operand_type == OperandType.QUBIT:
            # Should either be a qubit or an address read from memory
            try:
                self._assert_operand(operand, OperandType.READ)
            except TypeError:
                if not isinstance(operand, QubitAddress):
                    raise TypeError(f"Expected operand of type QubitAddress but got {type(operand)}")
        elif operand_type == OperandType.READ:
            if isinstance(operand, Address):
                pass
            elif isinstance(operand, Array):
                # If array, the index needs to be given
                if operand.index is None:
                    raise TypeError("When writing, an operand of type Array, needs a given index")
            else:
                raise TypeError(f"Expected operand of type Address or Array but got {type(operand)}")
        elif operand_type == OperandType.WRITE:
            if isinstance(operand, Address):
                address = operand
            elif isinstance(operand, Array):
                address = operand.address
            else:
                raise TypeError(f"Expected operand of type Address or Array but got {type(operand)}")

            if address.mode not in [AddressMode.DIRECT, AddressMode.INDIRECT]:
                raise ValueError(f"Expected address (direct or indirect) not a scalar (immediate)")

        elif operand_type == OperandType.ADDRESS:
            if not isinstance(operand, Address):
                raise TypeError(f"Expected operand of type Address but got {type(operand)}")
            if operand.mode not in [AddressMode.DIRECT, AddressMode.INDIRECT]:
                raise ValueError(f"Expected address (direct or indirect) not a scalar (immediate)")
        else:
            raise TypeError(f"Unknown operand type {type}")

    def _get_app_id(self, subroutine_id):
        """Returns the app ID for the given subroutine"""
        subroutine = self._subroutines.get(subroutine_id)
        if subroutine is None:
            raise ValueError(f"Unknown subroutine with ID {subroutine_id}")
        return subroutine.app_id
