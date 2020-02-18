import logging
from enum import Enum, auto
from types import GeneratorType
from collections import namedtuple

from netqasm.parser import Parser
from netqasm.encoder import Instruction
from netqasm.string_util import group_by_word
from netqasm.sdk.shared_memory import get_memory, SHARED_MEMORY_SIZE


class AddressMode(Enum):
    DIRECT = auto()
    IMMEDIATE = auto()


Operand = namedtuple("Operand", ["mode", "value", "index"])

OutputData = namedtuple("OutputData", ["address", "data"])


class Processor:

    def __init__(self, name=None, num_qubits=5):
        """Executes a sequence of NetQASM instructions.

        This is an abstract class where the method `get_next_subroutine` is required to be implemented.
        This method fetches the next subroutine (sequence of NetQASM instructions) to be executed.

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
            Optionally give a name to the processor for logging purposes.
            If `None`, the name is set to be the name of the class.
        num_qubits : int
            The number of qubits for the processor to use
        """

        if name is None:
            self._name = self.__class__.__name__
        else:
            self._name = name

        self._instruction_handlers = self._get_instruction_handlers()

        shared_memory_address = 0
        self._classical_registers = {
            shared_memory_address: self._allocate_new_classical_register(
                address=shared_memory_address,
                num_entries=SHARED_MEMORY_SIZE,
            ),
        }
        self._quantum_registers = {}

        self._outputted_data = []

        self._program_counter = 0

        self._logger = logging.getLogger(f"{self.__class__.__name__}({self._name})")

    @property
    def output_data(self):
        return self._outputted_data

    def reset(self):
        """Resets the program counter"""
        self._program_counter = 0

    def _get_instruction_handlers(self):
        """Creates the dictionary of instruction handlers"""
        instruction_handlers = {
            Instruction.CREG: self._instr_creg,
            Instruction.QREG: self._instr_qreg,
            Instruction.OUTPUT: self._instr_output,

            Instruction.INIT: self._instr_init,

            Instruction.ADD: self._instr_add,

            Instruction.H: self._instr_h,
            Instruction.X: self._instr_x,
            Instruction.MEAS: self._instr_meas,

            Instruction.BEQ: self._instr_beq,

            Instruction.CFREE: self._instr_cfree,
            Instruction.QFREE: self._instr_qfree,
        }
        return instruction_handlers

    def execute_instructions(self, instructions):
        """Executes the a subroutine given to the processor"""
        self.reset()
        output = self._execute_instructions(instructions)
        if not isinstance(output, GeneratorType):
            raise TypeError
        yield from output

    def _execute_instructions(self, instructions):
        """Executes a given subroutine"""
        while self._program_counter < len(instructions):
            instruction = instructions[self._program_counter]
            output = self._execute_instruction(instruction)
            if not isinstance(output, GeneratorType):
                raise TypeError
            yield from output

    def _execute_instruction(self, instruction):
        """Executes a single instruction and returns the new program counter"""
        instr, args, operands = self._parse_instruction(instruction)
        if instr not in self._instruction_handlers:
            raise RuntimeError(f"Unknown instruction identifier {instr} from {instruction}")
        try:
            output = self._instruction_handlers[instr](args, operands)
            if isinstance(output, GeneratorType):
                yield from output
        except TypeError as err:
            raise TypeError(f"Could not handle the instruction {instruction}, "
                            "was the number of arguments and operands correct? "
                            f"The error was: {err}")

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
            "creg": Instruction.CREG,
            "qreg": Instruction.QREG,
            "output": Instruction.OUTPUT,
            "init": Instruction.INIT,
            "add": Instruction.ADD,
            "h": Instruction.H,
            "x": Instruction.X,
            "meas": Instruction.MEAS,
            "beq": Instruction.BEQ,
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
        if operand[0] == Parser.ADDRESS_START:
            mode = AddressMode.DIRECT
            operand = operand[1:]
        else:
            mode = AddressMode.IMMEDIATE
        value, index = Parser._split_name_and_index(operand)
        value = int(value)
        if not index:
            index = None
        else:
            index = int(index[1:-1])
        return Operand(mode=mode, value=value, index=index)

    def _instr_creg(self, args, operands):
        self._assert_number_args(args, num=1)
        num_entries = args[0]
        self._assert_operands(operands, num=1, modes=[AddressMode.DIRECT], indexing=[False])
        address = operands[0].value

        if address in self._classical_registers:
            raise RuntimeError(f"Classical register with address {address} already exists")
        self._logger.debug(f"Adding a new classical register at address {address}")
        self._classical_registers[address] = self._allocate_new_classical_register(address, num_entries)
        self._program_counter += 1

    def _instr_qreg(self, args, operands):
        self._assert_number_args(args, num=1)
        num_entries = args[0]
        self._assert_operands(operands, num=1, modes=[AddressMode.DIRECT], indexing=[False])
        address = operands[0].value

        if address in self._quantum_registers:
            raise RuntimeError(f"Quantum register with address {address} already exists")
        self._logger.debug(f"Adding a new quantum register at address {address}")
        self._quantum_registers[address] = self._allocate_new_quantum_register(num_entries)
        self._program_counter += 1

    def _instr_output(self, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1, modes=[AddressMode.DIRECT], indexing=[False])
        self._output_data(operands[0].value)
        self._program_counter += 1

    def _output_data(self, address):
        self._logger.debug(f"Outputting data from register at address {address}")
        register = self._get_allocated_register(address, quantum=False)
        output_data = OutputData(address=address, data=register)
        # TODO should we copy?
        self._outputted_data.append(output_data)

    def _instr_init(self, args, operands):
        yield from self._handle_single_qubit_instr(Instruction.INIT, args, operands)
        self._program_counter += 1

    def _instr_add(self, args, operands):
        self._handle_binary_classical_instr(Instruction.ADD, args, operands)
        self._program_counter += 1

    def _instr_h(self, args, operands):
        yield from self._handle_single_qubit_instr(Instruction.H, args, operands)
        self._program_counter += 1

    def _instr_x(self, args, operands):
        yield from self._handle_single_qubit_instr(Instruction.X, args, operands)
        self._program_counter += 1

    def _instr_meas(self, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=2,
                              modes=[AddressMode.DIRECT, AddressMode.DIRECT],
                              indexing=[None, None])  # TODO what if inconsistent indexing?
        q_address = operands[0].value
        c_address = operands[1].value
        q_index = operands[0].index
        c_index = operands[1].index
        if q_index is None and c_index is None:
            self._logger.debug(f"Measuring all qubits in register with address {q_address}, "
                               f"placing the outcome at {c_address}")
            self._do_many_meas(q_address, c_address)
        else:
            if q_index is None:
                q_index = c_index
            if c_index is None:
                c_index = q_index
            self._logger.debug(f"Measuring the qubit with index {q_index} in register with address {q_address}, "
                               f"placing the outcome at {c_address} with index {c_index}")
            self._do_single_meas(q_address, c_index, c_address, c_index)

        self._program_counter += 1

    def _do_single_meas(self, q_address, q_index, c_address, c_index):
        """Performs a measurement on a single qubit"""
        pass

    def _do_many_meas(self, q_address, c_address):
        """Performs measurement on all qubits in a register"""
        q_register = self._get_allocated_register(q_address, quantum=True)
        for index in range(len(q_register)):
            self._do_single_meas(q_address, index, c_address, index)

    def _get_allocated_register(self, address, quantum=True):
        if quantum:
            registers = self._quantum_registers
            tp = "quantum"
        else:
            registers = self._classical_registers
            tp = "classical"
        if address not in registers:
            raise RuntimeError(f"The address {address} has no allocated {tp} register")
        return registers[address]

    def _instr_beq(self, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=3,
                              modes=[None, None, AddressMode.IMMEDIATE],
                              indexing=[True, True, False])
        a = self._get_address_value(operands[0])
        b = self._get_address_value(operands[1])
        jump_address = operands[2].value
        if a == b:
            self._program_counter = jump_address
        else:
            self._program_counter += 1

    def _instr_cfree(self, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1, modes=[AddressMode.DIRECT], indexing=[False])
        address = operands[0].value

        register = self._classical_registers.pop(address, None)
        if register is None:
            raise RuntimeError(f"The address {address} has no allocated classical register")
        self._logger.debug(f"Freeing classical register at address {address}")
        self._program_counter += 1

    def _instr_qfree(self, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1, modes=[AddressMode.DIRECT], indexing=[False])
        address = operands[0].value

        register = self._quantum_registers.pop(address, None)
        if register is None:
            raise RuntimeError(f"The address {address} has no allocated quantum register")
        self._logger.debug(f"Freeing quantum register at address {address}")
        self._program_counter += 1

    def _get_address_value(self, operand):
        if operand.mode == AddressMode.IMMEDIATE:
            return operand.value
        else:
            address = operand.value
            classical_register = self._get_allocated_register(address, quantum=False)
            if operand.index is None:
                raise RuntimeError("index needs to be set")
            return classical_register[operand.index]

    def _allocate_new_classical_register(self, address, num_entries):
        return _ClassicalRegister(
            node_name=self._name,
            address=address,
            num_entries=num_entries,
        )
        # return [0] * num_entries

    def _allocate_new_quantum_register(self, num_entries):
        return [None] * num_entries

    def _handle_single_qubit_instr(self, instr, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=1, modes=[AddressMode.DIRECT], indexing=[None])
        address = operands[0].value
        index = operands[0].index
        if index is None:
            self._logger.debug(f"Performing {instr} on all qubits in register at address {address}")
            yield from self._do_many_single_qubit_instr(instr, address)
        else:
            self._logger.debug(f"Performing {instr} on the qubit at index {index} in register at address {address}")
            yield from self._do_one_single_qubit_instr(instr, address, index)

    def _do_many_single_qubit_instr(self, instr, address):
        register = self._get_allocated_register(address, quantum=True)
        for index in range(len(register)):
            yield from self._do_one_single_qubit_instr(instr, address, index)

    def _do_one_single_qubit_instr(self, instr, address, index):
        """Performs a single qubit gate"""
        pass

    def _handle_binary_classical_instr(self, instr, args, operands):
        self._assert_number_args(args, num=0)
        self._assert_operands(operands, num=3, modes=[AddressMode.DIRECT, None, None],
                              indexing=[True, True, True])  # TODO allow non-indexing?
        a = self._get_address_value(operands[1])
        b = self._get_address_value(operands[2])
        value = self._compute_binary_classical_instr(instr, a, b)
        self._set_address_value(operands[0].value, operands[0].index, value=value)
        self._logger.debug(f"Performing {instr} of a={a} and b={b} "
                           f"and storing the value at address {operands[0].value}")

    def _compute_binary_classical_instr(self, instr, a, b):
        if instr == Instruction.ADD:
            return a + b
        else:
            raise RuntimeError("Unknown binary classical instructions {instr}")

    def _set_address_value(self, address, index, value):
        register = self._get_allocated_register(address, quantum=False)
        if index >= len(register):
            raise IndexError(f"Trying to set a value at index {index} for a register with only {len(register)} entries")
        register[index] = value

    def _assert_number_args(self, args, num):
        if not len(args) == num:
            raise TypeError(f"Expected {num} arguments, got {len(args)}")

    def _assert_operands(self, operands, num, modes, indexing):
        if not len(operands) == num:
            raise TypeError(f"Expected {num} operands, got {len(operands)}")
        for operand, mode, index in zip(operands, modes, indexing):
            if mode is not None:
                if operand.mode != mode:
                    raise TypeError(f"Expected operand in mode {mode} but got {operand.mode}")
            if operand.mode == AddressMode.DIRECT:  # We only need to check the index for direct mode
                if index is None:
                    pass
                elif index:
                    if operand.index is None:
                        raise TypeError("Expected operand with indexing")
                else:
                    if operand.index is not None:
                        raise TypeError("Expected operand without indexing")


class _ClassicalRegister:
    def __init__(self, node_name, address, num_entries):
        self._num_entries = num_entries
        self._address = address
        self._shared_memory = get_memory(node_name)

    def __len__(self):
        return self._num_entries

    def __setitem__(self, index, value):
        self._shared_memory[(self._address, index)] = value

    def __getitem__(self, index):
        value = self._shared_memory.get(self._address, index)
        if value is None:
            # This means that the value has not been set yet, return default 0
            return 0
        return value
