from collections import defaultdict, namedtuple
from itertools import count

from .string_util import group_by_word, is_variable_name, is_number
from .util import NetQASMSyntaxError, NetQASMInstrError


Subroutine = namedtuple("Subroutine", ["app_id", "netqasm_version", "instructions"])


class Parser:

    COMMENT_START = '//'
    INDEX_BRACKETS = '[]'
    BRANCH_END = ':'
    MACRO_END = '!'
    ADDRESS_START = '@'
    ARGS_BRACKETS = '()'
    ARGS_DELIM = ','

    PREAMBLE_START = '#'
    PREAMBLE_NETQASM = 'NETQASM'
    PREAMBLE_APPID = 'APPID'
    PREAMBLE_DEFINE = 'DEFINE'
    PREAMBLE_DEFINE_BRACKETS = r'{}'

    BUILT_IN_VARIABLES = {
        'sm': 0,  # Shared memory
    }

    def __init__(self, subroutine):
        """ Parses a given subroutine written in NetQASM.

        Parameters
        ----------
        subroutine : str
            A string with NetQASM instructions separated by line-breaks.
        """
        self._preamble_data, self._instructions = self._parse_subroutine(subroutine)
        self._branch_variables = None
        self._address_variables = None

    @property
    def netqasm_version(self):
        return self._preamble_data[self.__class__.PREAMBLE_NETQASM][0][0]

    @property
    def app_id(self):
        return self._preamble_data[self.__class__.PREAMBLE_APPID][0][0]

    @property
    def preamble_data(self):
        return self._preamble_data

    @property
    def instructions(self):
        return self._instructions

    @property
    def branch_variables(self):
        return self._branch_variables

    @property
    def address_variables(self):
        return self._address_variables

    def __str__(self):
        to_return = f"Parsed NetQASM subroutine (NETQASM: {self.netqasm_version}, APPID: {self.app_id}):\n\n"
        to_return += "\n".join([f"\t{instr}" for instr in self._instructions])
        return to_return

    def _parse_subroutine(self, subroutine):
        """Parses a subroutine and splits the preamble and body into separate parts."""
        preamble_lines, body_lines = self._split_preamble_body(subroutine)
        preamble_data = self._parse_preamble(preamble_lines)
        body_lines = self._apply_macros(body_lines, preamble_data[self.__class__.PREAMBLE_DEFINE])
        instructions = self._parse_body(body_lines)
        return preamble_data, instructions

    def _split_preamble_body(self, subroutine):
        """Splits the preamble from the body of the subroutine"""
        is_preamble = True
        preamble_lines = []
        body_lines = []
        for line in subroutine.split('\n'):
            # Remove surrounding whitespace and comments
            line = line.strip()
            line = self._remove_comments_from_line(line)
            if line == '':  # Ignore empty lines
                continue
            if line.startswith(self.__class__.PREAMBLE_START):
                if not is_preamble:  # Should not go out of preamble and in again
                    raise NetQASMSyntaxError("Cannot have a preamble line after instructions")
                line = line[1:].strip()
                if line == '':  # Ignore lines with only a '#' character
                    continue
                preamble_lines.append(line)
            else:
                is_preamble = False  # From now on the lines should not be part of the preamble
                body_lines.append(line)
        return preamble_lines, body_lines

    def _apply_macros(self, body_lines, macros):
        """Applies macros to the body lines"""
        body = "\n".join(body_lines)
        for macro_key, macro_value in macros:
            body = body.replace(f"{macro_key}{self.__class__.MACRO_END}", macro_value)
        return list(body.split('\n'))

    def _remove_comments_from_line(self, line):
        """Removes comments from a line"""
        return line.split(self.__class__.COMMENT_START)[0]

    def _parse_preamble(self, preamble_lines):
        """Parses the preamble lines"""
        preamble_instructions = defaultdict(list)
        for line in preamble_lines:
            try:
                instr, *operands = group_by_word(line, brackets=self.__class__.PREAMBLE_DEFINE_BRACKETS)
            except ValueError as err:
                raise NetQASMSyntaxError(f"Could not parse preamble instruction, since: {err}")
            preamble_instructions[instr].append(operands)
        self._assert_valid_preamble_instructions(preamble_instructions)
        return preamble_instructions

    def _assert_valid_preamble_instructions(self, preamble_instructions):
        preamble_assertions = {
            self.__class__.PREAMBLE_NETQASM: self._assert_valid_preamble_instr_netqasm,
            self.__class__.PREAMBLE_APPID: self._assert_valid_preamble_instr_appid,
            self.__class__.PREAMBLE_DEFINE: self._assert_valid_preamble_instr_define,
        }
        for instr, list_of_operands in preamble_instructions.items():
            preamble_assertion = preamble_assertions.get(instr)
            if preamble_assertion is None:
                raise NetQASMInstrError(f"The instruction {instr} is not a valid preamble instruction")
            preamble_assertion(list_of_operands)

    def _assert_valid_preamble_instr_netqasm(self, list_of_operands):
        self._assert_single_preamble_instr(list_of_operands, self.__class__.PREAMBLE_NETQASM)
        self._assert_single_preamble_arg(list_of_operands, self.__class__.PREAMBLE_NETQASM)

    def _assert_valid_preamble_instr_appid(self, list_of_operands):
        self._assert_single_preamble_instr(list_of_operands, self.__class__.PREAMBLE_APPID)
        self._assert_single_preamble_arg(list_of_operands, self.__class__.PREAMBLE_APPID)

    def _assert_valid_preamble_instr_define(self, list_of_operands):
        macro_keys = []
        for operands in list_of_operands:
            if len(operands) != 2:
                raise NetQASMSyntaxError(f"Preamble instruction {self.__class__.PREAMBLE_DEFINE} should contain "
                                         "exactly two argument, "
                                         f"not {len(operands)} as in '{operands}'")
            macro_key, macro_value = operands
            if not is_variable_name(macro_key):
                raise NetQASMInstrError(f"{macro_key} is not a valid macro key")
            macro_keys.append(macro_key)
        if len(set(macro_keys)) < len(macro_keys):
            raise NetQASMInstrError(f"Macro keys need to be unique, not {macro_keys}")

    def _assert_single_preamble_instr(self, list_of_operands, instr):
        if len(list_of_operands) != 1:
            raise NetQASMInstrError(f"Preamble should contain exactly one f{instr} instruction")

    def _assert_single_preamble_arg(self, list_of_operands, instr):
        for operands in list_of_operands:
            if len(operands) != 1:
                raise NetQASMSyntaxError(f"Preamble instruction {instr} should contain exactly one argument, "
                                         f"not {len(operands)} as in '{operands}'")

    def _parse_body(self, body_lines):
        """Parses the body lines"""
        # Apply built in variables
        body_lines = self._apply_built_in_variables(body_lines)
        print(body_lines)

        # Handle branch variables
        body_lines = self._assign_branch_variables(body_lines)

        # Handle address variables
        body_lines = self._assign_address_variables(body_lines)
        return body_lines

    def _apply_built_in_variables(self, body_lines):
        body_lines = self._update_variables(body_lines, self.__class__.BUILT_IN_VARIABLES, add_address_start=True)
        return body_lines

    def _assign_branch_variables(self, body_lines):
        """Finds the branch variables in a subroutine"""
        branch_variables = {}
        line_number = 0
        while line_number < len(body_lines):
            line = body_lines[line_number]
            # A line defining a branch variable should end with BRANCH_END
            if line[-1] != self.__class__.BRANCH_END:
                line_number += 1
                continue
            branch_variable = line[:-1]
            if not is_variable_name(line[:-1]):
                raise NetQASMSyntaxError(f"{branch_variable} is not a valid branch variable")
            if branch_variable in branch_variables:
                raise NetQASMSyntaxError("branch variables need to be unique, name {branch_variable} already used")
            branch_variables[branch_variable] = line_number
            body_lines = body_lines[:line_number] + body_lines[line_number + 1:]
        body_lines = self._update_variables(body_lines, branch_variables)

        self._branch_variables = branch_variables
        return body_lines

    def _assign_address_variables(self, body_lines):
        """Finds the address variables in a subroutine"""
        current_addresses = self._find_current_addresses(body_lines)
        address_variables = {}
        line_number = 0
        while line_number < len(body_lines):
            variable, var_line_number = self._find_next_variable(body_lines, line_number)
            if variable is None:  # No more variables
                break
            new_address = self._get_unused_address(current_addresses)
            current_addresses.append(new_address)
            address_variables[variable] = new_address
            body_lines = self._update_variables(body_lines, {variable: new_address},
                                                from_line=var_line_number,
                                                add_address_start=True)
            # Next time we search from where we found a variable
            # NOTE that there can be more than one per line
            line_number = var_line_number

        self._address_variables = address_variables
        return body_lines

    def _find_next_variable(self, body_lines, start_line_number):
        for line_number in range(start_line_number, len(body_lines)):
            line = body_lines[line_number]
            words = group_by_word(line)
            for word in words[1:]:
                # Split of indexing
                address, _ = self._split_name_and_index(word)
                if is_variable_name(address):
                    return address, line_number
        return None, -1

    def _find_current_addresses(self, body_lines):
        """Finds the used addresses in the body lines"""
        current_addresses = []
        for line in body_lines:
            words = group_by_word(line)
            for word in words[1:]:
                # Split of indexing
                address, _ = self._split_name_and_index(word)
                if not self._is_address(address):
                    continue
                address = address[1:]
                if is_number(address):
                    current_addresses.append(int(address))
        return current_addresses

    def _is_address(self, address):
        return (address[0] == self.__class__.ADDRESS_START) and is_number(address[1:])

    @staticmethod
    def _split_name_and_index(word):
        address, index = Parser._split_of_bracket(word, brackets=Parser.INDEX_BRACKETS)
        return address, index

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

    def _get_unused_address(self, current_addresses):
        for address in count(0):
            if address not in current_addresses:
                return address

    def _update_variables(self, body_lines, variables, from_line=0, add_address_start=False):
        """Updates variables in a subroutine with given values"""
        new_body_lines = body_lines[:from_line]
        for line in body_lines[from_line:]:
            line = self._update_variables_in_line(line, variables, add_address_start=add_address_start)
            new_body_lines.append(line)
        return new_body_lines

    def _update_variables_in_line(self, line, variables, add_address_start=False):
        words = group_by_word(line)
        new_words = []
        for word in words:
            word = self._update_variables_in_word(word, variables, add_address_start=add_address_start)
            new_words.append(word)
        return ' '.join(new_words)

    def _update_variables_in_word(self, word, variables, add_address_start=False):
        for variable, value in variables.items():
            # Split of indexing
            address, index = self._split_name_and_index(word)
            if address == variable:
                if variable == 'sm':
                    print("HELLO")
                new_word = f"{value}{index}"
                if add_address_start:
                    new_word = self.__class__.ADDRESS_START + new_word
                return new_word
        return word
