from enum import Enum, auto
from typing import List, Union
from itertools import count
from dataclasses import dataclass
from collections import defaultdict

from netqasm.string_util import group_by_word, is_variable_name, is_number, rspaces
from netqasm.util import NetQASMSyntaxError, NetQASMInstrError


class AddressMode(Enum):
    IMMEDIATE = auto()
    DIRECT = auto()
    INDIRECT = auto()


@dataclass
class Address:
    address: Union[int, str]
    mode: AddressMode

    def __str__(self):
        if self.mode == AddressMode.IMMEDIATE:
            return str(self.address)
        elif self.mode == AddressMode.DIRECT:
            if isinstance(self.address, int):
                return Parser.ADDRESS_START + str(self.address)
            else:
                return self.address
        elif self.mode == AddressMode.INDIRECT:
            if isinstance(self.address, int):
                return Parser.INDIRECT_START + str(self.address)
            else:
                return Parser.DEREF_START + self.address
        else:
            RuntimeError(f"Unknown addressing mode {self.mode}")


@dataclass
class QubitAddress:
    address: Union[str, int]

    def __str__(self):
        return Parser.QUBIT_START + str(self.address)


@dataclass
class Array:
    address: Address
    index: Union[None, Address]

    def __str__(self):
        return str(self.address) + Parser.INDEX_BRACKETS[0] + str(self.index) + Parser.INDEX_BRACKETS[1]


@dataclass
class Command:
    instruction: str
    args: List[int]
    operands: List[Union[Address, QubitAddress, Array]]

    def __str__(self):
        if len(self.args) == 0:
            args = ''
        else:
            args = Parser.ARGS_DELIM.join(str(arg) for arg in self.args)
            args = Parser.ARGS_BRACKETS[0] + args + Parser.ARGS_BRACKETS[1]
        operands = ' '.join(str(operand) for operand in self.operands)
        return f"{self.instruction}{args} {operands}"


@dataclass
class BranchVariable:
    name: str

    def __str__(self):
        return self.name + Parser.BRANCH_END


@dataclass
class Subroutine:
    netqasm_version: str
    app_id: int
    commands: List[Union[Command, BranchVariable]]

    def __str__(self):
        to_return = f"Subroutine (netqasm_version={self.netqasm_version}, app_id={self.app_id}):\n"
        for i, command in enumerate(self.commands):
            to_return += f"{rspaces(i)} {command}\n"
        return to_return


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
        self._branch_variables = None
        self._address_variables = None
        self._subroutine = self._parse_subroutine(subroutine)

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
    def qubit_address_variables(self):
        return self._address_variables.get("qubit")

    @property
    def classical_address_variables(self):
        return self._address_variables.get("classical")

    @property
    def subroutine(self):
        return self._subroutine

    def __str__(self):
        return f"Parser with parsed subroutine:\n{self.subroutine}"

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
            if line.endswith(Parser.BRANCH_END):
                # A command defining a branch variable should end with BRANCH_END
                commands.append(BranchVariable(line.rstrip(Parser.BRANCH_END)))
            else:
                words = group_by_word(line, brackets=Parser.ARGS_BRACKETS)
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
    def _split_instr_and_args(word):
        instr, args = Parser._split_of_bracket(word, brackets=Parser.ARGS_BRACKETS)
        return instr, args

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
            # QubitAddress
            address = word.lstrip(Parser.QUBIT_START)
            if is_number(address):
                return QubitAddress(int(address))
            else:
                return QubitAddress(word)
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
    def _parse_value(word):
        if word.startswith(Parser.DEREF_START):
            address = word.lstrip(Parser.INDIRECT_START)
            if is_number(address):
                address = int(address)
            return Address(address=address, mode=AddressMode.INDIRECT)
        elif word.startswith(Parser.ADDRESS_START):
            address = word.lstrip(Parser.ADDRESS_START)
            if not is_number(address):
                raise NetQASMSyntaxError(f"Expected number for address {address}")
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
        if len(body_lines) == 0:
            return []
        body = "\n".join(body_lines)
        for macro_key, macro_value in macros:
            macro_value = macro_value.strip(Parser.PREAMBLE_DEFINE_BRACKETS)
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

    def _assign_address_variables(self, subroutine):
        """Finds the address variables in a subroutine"""
        current_addresses = self.__class__._find_current_addresses(subroutine)
        address_variables = defaultdict(dict)
        command_number = 0
        while command_number < len(subroutine.commands):
            variable, var_command_number, var_type = self.__class__._find_next_variable(subroutine, command_number)
            if variable is None:  # No more variables
                break
            new_address = self.__class__._get_unused_address(current_addresses[var_type])
            current_addresses[var_type].add(new_address)
            address_variables[var_type][variable] = new_address
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
                if address is None:
                    continue
                if isinstance(address, int):
                    continue
                if is_variable_name(address):
                    type = "qubit" if isinstance(operand, QubitAddress) else "classical"
                    return address, command_number, type
                else:
                    raise NetQASMSyntaxError(f"Not a valid variable name {address}")
        return None, -1, None

    @staticmethod
    def _find_current_addresses(subroutine):
        """Finds the used addresses in the body lines"""
        current_addresses = defaultdict(set)
        for command in subroutine.commands:
            for operand in command.operands:
                address = Parser._get_address_from_operand(operand)
                if isinstance(address, int):
                    type = "qubit" if isinstance(operand, QubitAddress) else "classical"
                    current_addresses[type].add(address)
        return current_addresses

    @staticmethod
    def _get_address_from_operand(operand):
        if isinstance(operand, Address):
            if operand.mode == AddressMode.IMMEDIATE:
                return None
            else:
                return operand.address
        elif isinstance(operand, QubitAddress):
            return operand.address
        elif isinstance(operand, Array):
            return operand.address.address
        else:
            raise TypeError(f"Unknown operand type {type(operand)}")

    @staticmethod
    def _set_address_for_operand(operand, address):
        if isinstance(operand, Address):
            operand.address = address
        elif isinstance(operand, QubitAddress):
            operand.address = address
        elif isinstance(operand, Array):
            operand.address.address = address
        else:
            raise TypeError(f"Unknown operand type {type(operand)}")

    @staticmethod
    def _get_unused_address(current_addresses):
        for address in count(0):
            if address not in current_addresses:
                return address

    @staticmethod
    def _update_variables(subroutine, variables, from_command=0, mode=None):
        """Updates variables in a subroutine with given values"""
        for command in subroutine.commands[from_command:]:
            if isinstance(command, Command):
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

    @staticmethod
    def _find_current_branch_variables(subroutine: str):
        """Finds the current branch variables in a subroutine (str) and returns these as a list"""
        # NOTE preamble definitions are ignored
        # NOTE there is no checking here for valid and unique variable names
        preamble_lines, body_lines = Parser._split_preamble_body(subroutine)

        branch_variables = []
        for line in body_lines:
            # A line defining a branch variable should end with BRANCH_END
            if line.endswith(Parser.BRANCH_END):
                branch_variables.append(line.rstrip(Parser.BRANCH_END))

        return branch_variables
