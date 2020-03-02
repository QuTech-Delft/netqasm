from enum import Enum, auto
from typing import List, Union
from itertools import count
from dataclasses import dataclass
from collections import defaultdict, namedtuple

from netqasm.string_util import group_by_word, is_variable_name, is_number
from netqasm.util import NetQASMSyntaxError, NetQASMInstrError


Subroutine = namedtuple("Subroutine", ["app_id", "netqasm_version", "instructions"])


class OperandType(Enum):
    VALUE = auto()
    QUBIT = auto()
    ARRAY = auto()


class OffsetType(Enum):
    NONE = auto()
    INDEX = auto()


class AddressMode(Enum):
    IMMEDIATE = auto()
    DIRECT = auto()
    INDIRECT = auto()


# @dataclass
# class Offset:
#     base: int
#     offset: int


@dataclass
class Address:
    address: Union[int, str]
    mode: AddressMode


# @dataclass
# class Value:
#     address: int


@dataclass
class Qubit:
    address: Union[str, int]


@dataclass
class Array:
    address: Address
    index: Union[None, Address]


# @dataclass
# class Operand:
#     operand: Union[Value, Qubit, Array]


@dataclass
class Command:
    instruction: str
    args: List[int]
    operands: List[Union[Address, Qubit, Array]]


@dataclass
class BranchVariable:
    name: str


@dataclass
class Subroutine:
    netqasm_version: str
    app_id: int
    commands: List[Union[Command, BranchVariable]]


class Parser:

    COMMENT_START = '//'
    BRANCH_END = ':'
    MACRO_END = '!'
    ADDRESS_START = '@'
    DEREF_START = '*'
    INDIRECT_START = DEREF_START + ADDRESS_START
    ARGS_BRACKETS = '()'
    ARGS_DELIM = ','
    INDEX_BRACKETS = '[]'
    QUBIT_START = 'q'

    PREAMBLE_START = '#'
    PREAMBLE_NETQASM = 'NETQASM'
    PREAMBLE_APPID = 'APPID'
    PREAMBLE_DEFINE = 'DEFINE'
    PREAMBLE_DEFINE_BRACKETS = r'{}'

    BUILT_IN_VARIABLES = {
    }

    def __init__(self, subroutine):
        """ Parses a given subroutine written in NetQASM.

        Parameters
        ----------
        subroutine : str
            A string with NetQASM instructions separated by line-breaks.
        """
        self._subroutine = self._parse_subroutine(subroutine)
        self._branch_variables = None
        self._address_variables = None

    @property
    def netqasm_version(self):
        return self._subroutine.netqasm_version

    @property
    def app_id(self):
        return self._subroutine.app_id

    @property
    def commands(self):
        return self._subroutine.commands

    @property
    def branch_variables(self):
        return self._branch_variables

    @property
    def address_variables(self):
        return self._address_variables

    @property
    def subroutine(self):
        return self._subroutine

    def __str__(self):
        to_return = f"Parsed NetQASM subroutine (NETQASM: {self.netqasm_version}, APPID: {self.app_id}):\n\n"
        to_return += "\n".join([f"\t{instr}" for instr in self._instructions])
        return to_return

    def _parse_subroutine(self, subroutine):
        """Parses a subroutine and splits the preamble and body into separate parts."""
        preamble_lines, body_lines = self.__class__._split_preamble_body(subroutine)
        preamble_data = self.__class__._parse_preamble(preamble_lines)
        body_lines = self.__class__._apply_macros(body_lines, preamble_data[self.__class__.PREAMBLE_DEFINE])
        subroutine = self.__class__._create_subroutine(preamble_data, body_lines)
        self._parse_body(subroutine)
        return subroutine

    @staticmethod
    def _create_subroutine(preamble_data, body_lines):
        commands = []
        for line in body_lines:
            words = group_by_word(line)
            # A command defining a branch variable should end with BRANCH_END
            # TODO
            instr, args = Parser._split_instr_and_args(words[0])
            args = Parser._parse_args(args)
            operands = Parser._parse_operands(words[1:])
            command = Command(
                instruction=instr,
                args=args,
                operands=operands,
            )
            commands.append(command)

        return Subroutine(
            netqasm_version=preamble_data[Parser.PREAMBLE_NETQASM][0][0],
            app_id=int(preamble_data[Parser.PREAMBLE_APPID][0][0]),
            commands=commands,
        )

    @staticmethod
    def _parse_args(args):
        if args == "":
            return []
        else:
            return [int(arg.strip())
                    for arg in args.strip(Parser.ARGS_BRACKETS)
                    .split(Parser.ARGS_DELIM)]

    @staticmethod
    def _parse_operands(words):
        operands = []
        for word in words:
            operand = Parser._parse_operand(word)
            operands.append(operand)

        return operands

    @staticmethod
    def _parse_operand(word):
        if word.startswith(Parser.QUBIT_START):
            # Qubit
            address = word.lstrip(Parser.QUBIT_START)
            if is_number(address):
                return Qubit(int(address))
            else:
                return Qubit(word)
        elif Parser.INDEX_BRACKETS[0] in word:
            # Array
            array, index = Parser._split_of_bracket(word, Parser.INDEX_BRACKETS)
            if index == Parser.INDEX_BRACKETS:
                index = None
            else:
                index = Parser._parse_value(index.strip(Parser.INDEX_BRACKETS))
            array = Parser._parse_value(array)
            return Array(array, index)
        else:
            return Parser._parse_value(word)

    @staticmethod
    def _parse_value(word):
        if word.startswith(Parser.DEREF_START):
            address = word.lstrip(Parser.INDIRECT_START)
            if is_number(address):
                address = int(address)
            return Address(address=address, mode=AddressMode.INDIRECT)
        elif word.startswith(Parser.ADDRESS_START):
            address = word.lstrip(Parser.ADDRESS_START)
            if not is_number(address):
                raise NetQASMSyntaxError("Expected number for address {address}")
            return Address(address=int(address), mode=AddressMode.DIRECT)
        elif is_number(word):
            return Address(address=int(word), mode=AddressMode.IMMEDIATE)
        else:
            # Direct mode with a variable
            return Address(address=word, mode=AddressMode.DIRECT)

    @staticmethod
    def _split_preamble_body(subroutine):
        """Splits the preamble from the body of the subroutine"""
        is_preamble = True
        preamble_lines = []
        body_lines = []
        for line in subroutine.split('\n'):
            # Remove surrounding whitespace and comments
            line = line.strip()
            line = Parser._remove_comments_from_line(line)
            if line == '':  # Ignore empty lines
                continue
            if line.startswith(Parser.PREAMBLE_START):
                if not is_preamble:  # Should not go out of preamble and in again
                    raise NetQASMSyntaxError("Cannot have a preamble line after instructions")
                line = line.lstrip(Parser.PREAMBLE_START).strip()
                if line == Parser.PREAMBLE_START:  # Ignore lines with only a '#' character
                    continue
                preamble_lines.append(line)
            else:
                is_preamble = False  # From now on the lines should not be part of the preamble
                body_lines.append(line)
        return preamble_lines, body_lines

    @staticmethod
    def _apply_macros(body_lines, macros):
        """Applies macros to the body lines"""
        body = "\n".join(body_lines)
        for macro_key, macro_value in macros:
            body = body.replace(f"{macro_key}{Parser.MACRO_END}", macro_value)
        return list(body.split('\n'))

    @staticmethod
    def _remove_comments_from_line(line):
        """Removes comments from a line"""
        return line.split(Parser.COMMENT_START)[0]

    @staticmethod
    def _parse_preamble(preamble_lines):
        """Parses the preamble lines"""
        preamble_instructions = defaultdict(list)
        for line in preamble_lines:
            try:
                instr, *operands = group_by_word(line, brackets=Parser.PREAMBLE_DEFINE_BRACKETS)
            except ValueError as err:
                raise NetQASMSyntaxError(f"Could not parse preamble instruction, since: {err}")
            preamble_instructions[instr].append(operands)
        Parser._assert_valid_preamble_instructions(preamble_instructions)
        return preamble_instructions

    @staticmethod
    def _assert_valid_preamble_instructions(preamble_instructions):
        preamble_assertions = {
            Parser.PREAMBLE_NETQASM: Parser._assert_valid_preamble_instr_netqasm,
            Parser.PREAMBLE_APPID: Parser._assert_valid_preamble_instr_appid,
            Parser.PREAMBLE_DEFINE: Parser._assert_valid_preamble_instr_define,
        }
        for instr, list_of_operands in preamble_instructions.items():
            preamble_assertion = preamble_assertions.get(instr)
            if preamble_assertion is None:
                raise NetQASMInstrError(f"The instruction {instr} is not a valid preamble instruction")
            preamble_assertion(list_of_operands)

    @staticmethod
    def _assert_valid_preamble_instr_netqasm(list_of_operands):
        Parser._assert_single_preamble_instr(list_of_operands, Parser.PREAMBLE_NETQASM)
        Parser._assert_single_preamble_arg(list_of_operands, Parser.PREAMBLE_NETQASM)

    @staticmethod
    def _assert_valid_preamble_instr_appid(list_of_operands):
        Parser._assert_single_preamble_instr(list_of_operands, Parser.PREAMBLE_APPID)
        Parser._assert_single_preamble_arg(list_of_operands, Parser.PREAMBLE_APPID)

    @staticmethod
    def _assert_valid_preamble_instr_define(list_of_operands):
        macro_keys = []
        for operands in list_of_operands:
            if len(operands) != 2:
                raise NetQASMSyntaxError(f"Preamble instruction {Parser.PREAMBLE_DEFINE} should contain "
                                         "exactly two argument, "
                                         f"not {len(operands)} as in '{operands}'")
            macro_key, macro_value = operands
            if not is_variable_name(macro_key):
                raise NetQASMInstrError(f"{macro_key} is not a valid macro key")
            macro_keys.append(macro_key)
        if len(set(macro_keys)) < len(macro_keys):
            raise NetQASMInstrError(f"Macro keys need to be unique, not {macro_keys}")

    @staticmethod
    def _assert_single_preamble_instr(list_of_operands, instr):
        if len(list_of_operands) != 1:
            raise NetQASMInstrError(f"Preamble should contain exactly one f{instr} instruction")

    @staticmethod
    def _assert_single_preamble_arg(list_of_operands, instr):
        for operands in list_of_operands:
            if len(operands) != 1:
                raise NetQASMSyntaxError(f"Preamble instruction {instr} should contain exactly one argument, "
                                         f"not {len(operands)} as in '{operands}'")

    def _parse_body(self, subroutine):
        """Parses the body lines"""
        # Apply built in variables
        self.__class__._apply_built_in_variables(subroutine)

        # Handle branch variables
        self._assign_branch_variables(subroutine)

        # Handle address variables
        self._assign_address_variables(subroutine)
        return subroutine

    @staticmethod
    def _apply_built_in_variables(subroutine):
        Parser._update_variables(subroutine, Parser.BUILT_IN_VARIABLES)

    def _assign_branch_variables(self, subroutine):
        """Finds the branch variables in a subroutine"""
        branch_variables = {}
        command_number = 0
        commands = subroutine.commands
        while command_number < len(commands):
            command = commands[command_number]
            # A command defining a branch variable should end with BRANCH_END
            if not isinstance(command, BranchVariable):
                command_number += 1
                continue
            branch_variable = command.name
            if not is_variable_name(branch_variable):
                raise NetQASMSyntaxError(f"{branch_variable} is not a valid branch variable")
            if branch_variable in branch_variables:
                raise NetQASMSyntaxError("branch variables need to be unique, name {branch_variable} already used")
            branch_variables[branch_variable] = command_number
            commands = commands[:command_number] + commands[command_number + 1:]
        subroutine.commands = commands
        self.__class__._update_variables(subroutine, branch_variables, mode=AddressMode.IMMEDIATE)

        self._branch_variables = branch_variables

    @staticmethod
    def _find_current_branch_variables(subroutine):
        """Finds the current branch variables in a subroutine and returns these as a list"""
        # NOTE preamble definitions are ignored
        # NOTE there is no checking here for valid and unique variable names
        # TODO
        preamble_lines, body_lines = Parser._split_preamble_body(subroutine)

        branch_variables = []
        for line in body_lines:
            # A line defining a branch variable should end with BRANCH_END
            if line.endswith(Parser.BRANCH_END):
                branch_variables.append(line.rstrip(Parser.BRANCH_END))

        return branch_variables

    def _assign_address_variables(self, subroutine):
        """Finds the address variables in a subroutine"""
        current_addresses = self.__class__._find_current_addresses(subroutine)
        address_variables = {}
        command_number = 0
        while command_number < len(subroutine.commands):
            variable, var_command_number = self.__class__._find_next_variable(subroutine, command_number)
            if variable is None:  # No more variables
                break
            new_address = self.__class__._get_unused_address(current_addresses)
            current_addresses.add(new_address)
            address_variables[variable] = new_address
            self.__class__._update_variables(subroutine, {variable: new_address},
                                             from_command=var_command_number)
            # Next time we search from where we found a variable
            # NOTE that there can be more than one per line
            command_number = var_command_number

        self._address_variables = address_variables

    @staticmethod
    def _find_next_variable(subroutine, start_command_number):
        for command_number in range(start_command_number, len(subroutine.commands)):
            command = subroutine.commands[command_number]
            for operand in command.operands:
                address = Parser._get_address_from_operand(operand)
                if isinstance(address, int):
                    continue
                if is_variable_name(address):
                    return address, command_number
                else:
                    breakpoint()
                    raise NetQASMSyntaxError(f"Not a valid variable name {address}")
        return None, -1

    @staticmethod
    def _ignore_deref(address):
        return address.lstrip(Parser.DEREF_START)

    @staticmethod
    def _get_address_from_operand(operand):
        if isinstance(operand, Address):
            return operand.address
        elif isinstance(operand, Qubit):
            return operand.address
        elif isinstance(operand, Array):
            return operand.address.address
        else:
            raise TypeError(f"Unknown operand type {type(operand)}")

    @staticmethod
    def _set_address_for_operand(operand, address):
        if isinstance(operand, Address):
            operand.address = address
        elif isinstance(operand, Qubit):
            operand.address = address
        elif isinstance(operand, Array):
            operand.address.address = address
        else:
            raise TypeError(f"Unknown operand type {type(operand)}")

    @staticmethod
    def _find_current_addresses(subroutine):
        """Finds the used addresses in the body lines"""
        current_addresses = set([])
        for command in subroutine.commands:
            for operand in command.operands:
                address = Parser._get_address_from_operand(operand)
                if isinstance(address, int):
                    current_addresses.add(address)
        return current_addresses

    @staticmethod
    def _is_address(address):
        address = Parser._ignore_address_mode(address)
        return is_number(address)

    @staticmethod
    def _ignore_address_mode(address):
        if address.startswith(Parser.ADDRESS_START):
            return address.lstrip(Parser.ADDRESS_START)
        elif address.startswith(Parser.INDIRECT_START):
            return address.lstrip(Parser.INDIRECT_START)
        else:
            # IMMEDIATE mode (not an address)
            return None

    @staticmethod
    def _split_instr_and_args(word):
        instr, args = Parser._split_of_bracket(word, brackets=Parser.ARGS_BRACKETS)
        return instr, args

    @staticmethod
    def _split_of_bracket(word, brackets):
        start_bracket, end_bracket = brackets
        start = word.find(start_bracket)
        if start == -1:
            return word, ""
        if word[-1] != end_bracket:
            raise NetQASMSyntaxError(f"No end bracket in {word}, expected '{end_bracket}'")
        address = word[:start]
        content = word[start:]
        return address, content

    @staticmethod
    def _get_unused_address(current_addresses):
        for address in count(0):
            if address not in current_addresses:
                return address

    @staticmethod
    def _update_variables(subroutine, variables, from_command=0, mode=None):
        """Updates variables in a subroutine with given values"""
        for command in subroutine.commands[from_command:]:
            Parser._update_variables_in_command(command, variables, mode=mode)

    @staticmethod
    def _update_variables_in_command(command, variables, mode=None):
        for operand in command.operands:
            Parser._update_variables_in_operand(operand, variables, mode=mode)

    @staticmethod
    def _update_variables_in_operand(operand, variables, mode=None):
        for variable, value in variables.items():
            address = Parser._get_address_from_operand(operand)
            if address == variable:
                Parser._set_address_for_operand(operand, value)
            if mode is not None:
                operand.mode = mode


def test():
    subroutine = """# NETQASM 0.0
# APPID 0
store @0 1
store *@0 1
store m 0
array(4) ms
add m m 1
add ms[0] m 1
beq 0 0 EXIT
EXIT:
"""

    parser = Parser(subroutine)
    print(parser.subroutine)
    for command in parser.subroutine.commands:
        print(command)


if __name__ == '__main__':
    test()
