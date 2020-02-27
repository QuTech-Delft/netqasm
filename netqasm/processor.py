import logging
from enum import Enum, auto
from types import GeneratorType
from collections import namedtuple, defaultdict
from itertools import count

from netqasm.parser import Parser
from netqasm.encoder import Instruction
from netqasm.string_util import group_by_word
from netqasm.sdk.shared_memory import get_shared_memory


class AddressMode(Enum):
    DIRECT = auto()
    INDIRECT = auto()
    IMMEDIATE = auto()


Operand = namedtuple("Operand", ["mode", "value"])

OutputData = namedtuple("OutputData", ["address", "data"])


def inc_program_counter(method):
    def new_method(self, subroutine_id, args, operands):
        output = method(self, subroutine_id, args, operands)
        if isinstance(output, GeneratorType):
            yield from output
        self._program_counters[subroutine_id] += 1
    return new_method


class Processor:

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
            Give a name to the processor for logging purposes.
        num_qubits : int
            The number of qubits for the processor to use
        """

        if name is None:
            self._name = f"{self.__class__}"
        else:
            self._name = name

        self._instruction_handlers = self._get_instruction_handlers()

        self._shared_memories = {}

        self._qubit_unit_modules = {}

        # There will be seperate program counters for each subroutine
        self._program_counters = defaultdict(int)

        # Keep track of what subroutines are currently handled
        self._subroutines = {}

        # Keep track of what physical qubit addresses are in use
        self._used_physical_qubit_addresses = []

        self._logger = logging.getLogger(f"{self.__class__.__name__}({self._name})")

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
        """Clears a subroutine from the processor"""
        self.reset_program_counter()
        self._subroutines.pop(subroutine_id, 0)

    def _get_instruction_handlers(self):
        """Creates the dictionary of instruction handlers"""
        instruction_handlers = {
            Instruction.QTAKE: self._instr_qtake,
            Instruction.INIT: self._instr_init,
            Instruction.STORE: self._instr_store,
            Instruction.ADD: self._instr_add,
            Instruction.H: self._instr_h,
            Instruction.X: self._instr_x,
            Instruction.MEAS: self._instr_meas,
            Instruction.BEQ: self._instr_beq,
            Instruction.QFREE: self._instr_qfree,
        }
        return instruction_handlers

    def execute_subroutine(self, subroutine):
        """Executes the a subroutine given to the processor"""
        subroutine_id = self._get_new_subroutine_id()
        self._subroutines[subroutine_id] = subroutine
        self.reset_program_counter(subroutine_id)
        output = self._execute_instructions(subroutine_id, subroutine.instructions)
        if isinstance(output, GeneratorType):
            yield from output

    def _get_new_subroutine_id(self):
        for subroutine_id in count(0):
            if subroutine_id not in self._subroutines:
                return subroutine_id

    def _execute_instructions(self, subroutine_id, instructions):
        """Executes a given subroutine"""
        while self._program_counters[subroutine_id] < len(instructions):
            instruction = instructions[self._program_counters[subroutine_id]]
            output = self._execute_instruction(subroutine_id, instruction)
            if isinstance(output, GeneratorType):
                yield from output

    def _execute_instruction(self, subroutine_id, instruction):
        """Executes a single instruction"""
        instr, args, operands = self._parse_instruction(instruction)
        if instr not in self._instruction_handlers:
            raise RuntimeError(f"Unknown instruction identifier {instr} from {instruction}")
        output = self._instruction_handlers[instr](subroutine_id, args, operands)
        if isinstance(output, GeneratorType):
            yield from output

    def _parse_instruction(self, instruction):
        # TODO should be handled differently when there is a binary encoding
        instr_args, *operands = group_by_word(instruction)
        instr, args = Parser._split_instr_and_args(instr_args)
        args = self._parse_args(args)
        instr = self._parse_instruction_id(instr)
        operands = self._parse_operands(operands)
        return instr, args, operands

    def _parse_instruction_id(self, instr):
        # TODO should be handled differently when there is a binary encoding
        instructions = {
            "qtake": Instruction.QTAKE,
            "init": Instruction.INIT,
            "store": Instruction.STORE,
            "add": Instruction.ADD,
            "h": Instruction.H,
            "x": Instruction.X,
            "meas": Instruction.MEAS,
            "beq": Instruction.BEQ,
            "qfree": Instruction.QFREE,
            }
        if instr not in instructions:
            raise RuntimeError(f"Instruction '{instr}' is not a known instruction")
        return instructions[instr]

    def _parse_operands(self, operands):
        return [self._parse_operand(operand) for operand in operands]

    def _parse_args(self, args):
        # TODO should be handled differently when there is a binary encoding
        if args == "":
            return []
        args = args[1:-1]
        return [int(arg.strip()) for arg in args.split(Parser.ARGS_DELIM)]

    def _parse_operand(self, operand):
        # TODO should be handled differently when there is a binary encoding
        if operand.startswith(Parser.INDIRECT_START):
            mode = AddressMode.INDIRECT
            value = int(operand[2:])
        elif operand.startswith(Parser.ADDRESS_START):
            mode = AddressMode.DIRECT
            value = int(operand[1:])
        else:
            mode = AddressMode.IMMEDIATE
            value = int(operand)
        return Operand(mode=mode, value=value)

    @inc_program_counter
    def _instr_qtake(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1,
                              modes=[AddressMode.DIRECT])
        address = operands[0].value
        self._allocate_physical_qubit(subroutine_id, address)
        self._logger.debug(f"Taking qubit at address {address}")

    @inc_program_counter
    def _instr_init(self, subroutine_id, args, operands):
        yield from self._handle_single_qubit_instr(Instruction.INIT, subroutine_id, args, operands)

    @inc_program_counter
    def _instr_store(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=2, modes=[
            [AddressMode.DIRECT, AddressMode.INDIRECT],
            None,
        ])
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        address = self._get_address(app_id=app_id, operand=operands[0])
        value = self._get_address_value(app_id=app_id, operand=operands[1])
        self._set_address_value(app_id=app_id, address=address, value=value)
        self._logger.debug(f"Storing value {value} at address {address}")

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
    def _instr_meas(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=2,
                              modes=[
                                  [AddressMode.DIRECT, AddressMode.INDIRECT],
                                  [AddressMode.DIRECT, AddressMode.INDIRECT]
                              ])
        q_address = operands[0].value
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        c_address = self._get_address(app_id=app_id, operand=operands[1])
        self._logger.debug(f"Measuring the qubit at address {q_address}, "
                           f"placing the outcome at address {c_address}")
        self._do_meas(subroutine_id, q_address, c_address)

    def _do_meas(self, subroutine_id, q_address, c_address):
        """Performs a measurement on a single qubit"""
        # Always give outcome zero in the default debug class
        outcome = 0
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        try:
            self._set_address_value(app_id=app_id, address=c_address, value=outcome)
        except IndexError:
            logging.warning("Measurement outcome dropped since no more entries in classical register")

    def _instr_beq(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=3,
                              modes=[None, None, AddressMode.IMMEDIATE])
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        a = self._get_address_value(app_id=app_id, operand=operands[0])
        b = self._get_address_value(app_id=app_id, operand=operands[1])
        jump_address = operands[2].value
        if a == b:
            self._logger.debug(f"Branching to line {jump_address} since {a} = {b} "
                               f"from address {operands[0]} and {operands[1]}")
            self._program_counters[subroutine_id] = jump_address
        else:
            self._logger.debug(f"Don't branch, since {a} =! {b} "
                               f"from address {operands[0]} and {operands[1]}")
            self._program_counters[subroutine_id] += 1

    @inc_program_counter
    def _instr_qfree(self, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1, modes=[AddressMode.DIRECT])
        address = operands[0].value

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

    def _get_address_value(self, app_id, operand):
        if operand.mode == AddressMode.IMMEDIATE:
            return operand.value
        elif operand.mode == AddressMode.DIRECT:
            address = operand.value
            shared_memory = self._shared_memories[app_id]
            if address >= len(shared_memory):
                raise IndexError(f"Trying to get a value at address {address} which is outside "
                                 f"the size ({len(shared_memory)}) of the shared memory")
            return shared_memory[address]
        else:
            # AddressMode.INDIRECT
            shared_memory = self._shared_memories[app_id]
            value = operand.value
            for _ in range(2):
                address = value
                if address >= len(shared_memory):
                    raise IndexError(f"Trying to get a value at address {address} which is outside "
                                     f"the size ({len(shared_memory)}) of the shared memory")
                value = shared_memory[address]
            return value

    def _get_address(self, app_id, operand):
        if operand.mode == AddressMode.IMMEDIATE:
            raise ValueError("Not an address mode")
        elif operand.mode == AddressMode.DIRECT:
            return operand.value
        else:
            # AddressMode.INDIRECT
            address = operand.value
            shared_memory = self._shared_memories[app_id]
            if address >= len(shared_memory):
                raise IndexError(f"Trying to get a value at address {address} which is outside "
                                 f"the size ({len(shared_memory)}) of the shared memory")
            return shared_memory[address]

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
            raise RuntimeError(f"Qubit at address {address} for application {app_id} is already allocated")

    def _free_physical_qubit(self, subroutine_id, address):
        unit_module = self._get_unit_module(subroutine_id)
        if unit_module[address] is None:
            app_id = self._subroutines[subroutine_id].app_id
            raise RuntimeError(f"Qubit at address {address} for application {app_id} is not allocated "
                               "and cannot be freed")
        else:
            unit_module[address] = None

    def _get_unused_physical_qubit(self, address):
        # Assuming that the topology of the unit module is a complete graph
        # is does not matter which unused physical qubit we choose for now
        for physical_address in count(0):
            if physical_address not in self._used_physical_qubit_addresses:
                return physical_address

    def _handle_single_qubit_instr(self, instr, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1, modes=[AddressMode.DIRECT])
        address = operands[0].value
        self._logger.debug(f"Performing {instr} on the qubit at address {address}")
        output = self._do_single_qubit_instr(instr, subroutine_id, address)
        if isinstance(output, GeneratorType):
            yield from output

    def _do_single_qubit_instr(self, instr, app_id, address):
        """Performs a single qubit gate"""
        pass

    def _handle_binary_classical_instr(self, instr, subroutine_id, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=3, modes=[AddressMode.DIRECT, None, None])
        app_id = self._get_app_id(subroutine_id=subroutine_id)
        a = self._get_address_value(app_id=app_id, operand=operands[1])
        b = self._get_address_value(app_id=app_id, operand=operands[2])
        value = self._compute_binary_classical_instr(instr, a, b)
        self._set_address_value(app_id=app_id, address=operands[0].value, value=value)
        self._logger.debug(f"Performing {instr} of a={a} and b={b} "
                           f"and storing the value at address {operands[0].value}")

    def _compute_binary_classical_instr(self, instr, a, b):
        if instr == Instruction.ADD:
            return a + b
        else:
            raise RuntimeError("Unknown binary classical instructions {instr}")

    def _set_address_value(self, app_id, address, value):
        shared_memory = self._shared_memories[app_id]
        if address >= len(shared_memory):
            raise IndexError(f"Trying to set a value at address {address} which is outside "
                             f"the size ({len(shared_memory)}) of the shared memory")
        shared_memory[address] = value

    def _assert_number_args(self, args, num):
        if not len(args) == num:
            raise TypeError(f"Expected {num} arguments, got {len(args)}")

    def _assert_operands(self, operands, num, modes):
        if not len(operands) == num:
            raise TypeError(f"Expected {num} operands, got {len(operands)}")
        for operand, mode in zip(operands, modes):
            if mode is not None:
                if not (operand.mode == mode or operand.mode in mode):
                    raise TypeError(f"Expected operand in mode {mode} but got {operand.mode}")

    def _get_app_id(self, subroutine_id):
        """Returns the app ID for the given subroutine"""
        subroutine = self._subroutines.get(subroutine_id)
        if subroutine is None:
            raise ValueError(f"Unknown subroutine with ID {subroutine_id}")
        return subroutine.app_id
