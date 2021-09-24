from collections import defaultdict
from itertools import count
from typing import Dict, List, Optional, Set, Tuple, Union

from netqasm.lang.encoding import REG_INDEX_BITS, RegisterName
from netqasm.lang.instr import Flavour, VanillaFlavour
from netqasm.lang.ir import (
    BranchLabel,
    GenericInstr,
    ICmd,
    PreSubroutine,
    string_to_instruction,
)
from netqasm.lang.operand import Address, ArrayEntry, ArraySlice, Label, Register
from netqasm.lang.subroutine import Subroutine
from netqasm.lang.symbols import Symbols
from netqasm.util.error import NetQASMInstrError, NetQASMSyntaxError
from netqasm.util.string import group_by_word, is_number, is_variable_name

T_Cmd = Union[ICmd, BranchLabel]
T_ParsedValue = Union[int, Register, Label]


def parse_text_presubroutine(text: str) -> PreSubroutine:
    """
    Convert a text representation of a subroutine into a PreSubroutine object.
    """
    preamble_lines, body_lines_with_macros = _split_preamble_body(text)
    preamble_data = _parse_preamble(preamble_lines)
    body_lines = _apply_macros(
        body_lines_with_macros, preamble_data[Symbols.PREAMBLE_DEFINE]
    )
    return _create_subroutine(preamble_data, body_lines)


def parse_text_subroutine(
    subroutine: str,
    assign_branch_labels=True,
    make_args_operands=True,
    replace_constants=True,
    flavour: Flavour = None,
) -> Subroutine:
    """
    Convert a text representation of a subroutine into a Subroutine object.

    Internally, first a `PreSubroutine` object is created, consisting of `ICmd`s.
    This is then converted into a `Subroutine` using `assemble_subroutine`.
    """
    pre_subroutine = parse_text_presubroutine(subroutine)
    assembled_subroutine = assemble_subroutine(
        pre_subroutine=pre_subroutine,
        assign_branch_labels=assign_branch_labels,
        make_args_operands=make_args_operands,
        replace_constants=replace_constants,
        flavour=flavour,
    )
    return assembled_subroutine


def assemble_subroutine(
    pre_subroutine: PreSubroutine,
    assign_branch_labels=True,
    make_args_operands=True,
    replace_constants=True,
    flavour: Flavour = None,
) -> Subroutine:
    """
    Convert a `PreSubroutine` into a `Subroutine`, given a Flavour (default: vanilla).
    """
    if make_args_operands:
        _make_args_operands(pre_subroutine)
    if replace_constants:
        pre_subroutine.commands = _replace_constants(pre_subroutine.commands)
    if assign_branch_labels:
        _assign_branch_labels(pre_subroutine)

    if flavour is None:
        flavour = VanillaFlavour()
    subroutine = _build_subroutine(pre_subroutine, flavour)

    return subroutine


def _build_subroutine(pre_subroutine: PreSubroutine, flavour: Flavour) -> Subroutine:
    subroutine = Subroutine(
        netqasm_version=pre_subroutine.netqasm_version,
        app_id=pre_subroutine.app_id,
        commands=[],
    )

    for command in pre_subroutine.commands:
        assert isinstance(command, ICmd)

        instr = flavour.get_instr_by_name(command.instruction.name.lower())
        new_command = instr.from_operands(command.operands)
        new_command.lineno = command.lineno

        subroutine.commands.append(new_command)
    return subroutine


def _create_subroutine(preamble_data, body_lines: List[str]) -> PreSubroutine:
    commands: List[Union[ICmd, BranchLabel]] = []
    for line in body_lines:
        if line.endswith(Symbols.BRANCH_END):
            # A command defining a branch label should end with BRANCH_END
            branch_label = line.rstrip(Symbols.BRANCH_END)
            if not is_variable_name(branch_label):
                raise NetQASMSyntaxError(
                    f"The branch label {branch_label} is not a valid label"
                )
            commands.append(BranchLabel(branch_label))
        else:
            words: List[str] = group_by_word(line, brackets=Symbols.ARGS_BRACKETS)
            instr_name, args = _split_instr_and_args(words[0])
            instr = string_to_instruction(instr_name)
            args = _parse_args(args)
            operands = _parse_operands(words[1:])
            command = ICmd(
                instruction=instr,
                args=args,
                operands=operands,
            )
            commands.append(command)

    return PreSubroutine(
        netqasm_version=_parse_netqasm_version(
            preamble_data[Symbols.PREAMBLE_NETQASM][0][0]
        ),
        app_id=int(preamble_data[Symbols.PREAMBLE_APPID][0][0]),
        commands=commands,
    )


def _parse_netqasm_version(netqasm_version):
    try:
        major, minor = netqasm_version.strip().split(".")
        return int(major), int(minor)
    except Exception as err:
        raise ValueError(
            f"Could not parse netqasm version {netqasm_version} since: {err}"
        )


def _split_instr_and_args(word):
    instr, args = _split_of_bracket(word, brackets=Symbols.ARGS_BRACKETS)
    return instr, args


def _parse_args(args):
    if args == "":
        return []
    else:
        return [
            _parse_constant(arg.strip())
            for arg in args.strip(Symbols.ARGS_BRACKETS).split(Symbols.ARGS_DELIM)
        ]


def _parse_constant(constant: str) -> int:
    if not is_number(constant):
        raise NetQASMSyntaxError(f"Expected constant, got {constant}")
    return int(constant)


def _parse_operands(words: List[str]):
    operands = []
    for word in words:
        operand = _parse_operand(word.strip())
        operands.append(operand)

    return operands


def _parse_operand(word: str):
    if word.startswith(Symbols.ADDRESS_START):
        return parse_address(word)
    else:
        return _parse_value(word, allow_label=True)


def _parse_value(value: str, allow_label: bool = False) -> T_ParsedValue:
    # Try to parse a constant
    try:
        return _parse_constant(value)
    except NetQASMSyntaxError:
        pass

    # Try to parse a register
    try:
        return parse_register(value)
    except NetQASMSyntaxError:
        pass

    if allow_label:
        # Parse a label
        try:
            return _parse_label(value)
        except NetQASMSyntaxError:
            pass

    raise NetQASMSyntaxError(f"{value} is not a valid value in this case")


def _is_byte(value):
    if not value.startswith("0x"):
        return False
    if not len(value) == 4:
        return False
    return is_number(value[2:])


def _parse_label(label: str) -> Label:
    if not is_variable_name(label):
        raise NetQASMSyntaxError(f"Expected a label, got {label}")
    return Label(label)


_REGISTER_NAMES = {reg.name: reg for reg in RegisterName}


def parse_register(register: str) -> Register:
    try:
        register_name = _REGISTER_NAMES[register[0]]
    except KeyError:
        raise NetQASMSyntaxError(f"{register[0]} is not a valid register name")
    value = _parse_constant(register[1:])
    return Register(register_name, value)


def parse_address(address: str) -> Union[Address, ArraySlice, ArrayEntry]:
    base_address, index_str = _split_of_bracket(address, Symbols.INDEX_BRACKETS)
    base_address_int: int = _parse_base_address(base_address)
    index = _parse_index(index_str)
    address_parsed = Address(base_address_int)
    if index is None:
        return address_parsed
    elif isinstance(index, tuple):
        if (not isinstance(index[0], Register) and not isinstance(index[0], int)) or (
            not isinstance(index[1], Register) and not isinstance(index[1], int)
        ):
            raise TypeError(
                f"indices {index[0]} and {index[1]} should be ints or Registers,"
                f" not {type(index[0])} and {type(index[1])}"
            )
        return ArraySlice(address_parsed, start=index[0], stop=index[1])
    elif isinstance(index, int) or isinstance(index, Register):
        return ArrayEntry(address_parsed, index)
    else:
        raise TypeError(f"Index cannot have type {type(index)}")


def _parse_base_address(base_address: str) -> int:
    if not base_address.startswith(Symbols.ADDRESS_START):
        raise NetQASMSyntaxError(f"Expected address, got {base_address}")
    value = _parse_value(base_address.lstrip(Symbols.ADDRESS_START))
    if not isinstance(value, int):
        raise TypeError(f"Address should be an int, not a {type(value)}")
    return value


def _parse_index(
    index: str,
) -> Optional[Union[T_ParsedValue, Tuple[T_ParsedValue, T_ParsedValue]]]:
    if index == "":
        return None
    index = index.strip(Symbols.INDEX_BRACKETS).strip()
    if Symbols.SLICE_DELIM in index:
        start, stop = index.split(Symbols.SLICE_DELIM)
        return _parse_value(start.strip()), _parse_value(stop.strip())
    else:
        return _parse_value(index)


def _split_of_bracket(word: str, brackets: str) -> Tuple[str, str]:
    if len(brackets) != 2:
        raise ValueError(f"`brackets` cannot be {brackets}")
    start_bracket: str = brackets[0]
    end_bracket: str = brackets[1]
    start = word.find(start_bracket)
    if start == -1:
        return word, ""
    if word[-1] != end_bracket:
        raise NetQASMSyntaxError(f"No end bracket in {word}, expected '{end_bracket}'")
    address = word[:start]
    content = word[start:]
    return address, content


def _split_preamble_body(subroutine_text: str) -> Tuple[List[str], List[str]]:
    """Splits the preamble from the body of the subroutine"""
    is_preamble = True
    preamble_lines = []
    body_lines = []
    for line in subroutine_text.split("\n"):
        # Remove surrounding whitespace and comments
        line = line.strip()
        line = _remove_comments_from_line(line)
        if line == "":  # Ignore empty lines
            continue
        if line.startswith(Symbols.PREAMBLE_START):
            if not is_preamble:  # Should not go out of preamble and in again
                raise NetQASMSyntaxError(
                    "Cannot have a preamble line after instructions"
                )
            line = line.lstrip(Symbols.PREAMBLE_START).strip()
            if line == Symbols.PREAMBLE_START:  # Ignore lines with only a '#' character
                continue
            preamble_lines.append(line)
        else:
            is_preamble = (
                False  # From now on the lines should not be part of the preamble
            )
            body_lines.append(line)
    return preamble_lines, body_lines


def _apply_macros(body_lines, macros) -> List[str]:
    """Applies macros to the body lines"""
    if len(body_lines) == 0:
        return []
    body = "\n".join(body_lines)
    for macro_key, macro_value in macros:
        macro_value = macro_value.strip(Symbols.PREAMBLE_DEFINE_BRACKETS)
        body = body.replace(f"{Symbols.MACRO_START}{macro_key}", macro_value)
    return list(body.split("\n"))


def _remove_comments_from_line(line):
    """Removes comments from a line"""
    return line.split(Symbols.COMMENT_START)[0]


def _parse_preamble(preamble_lines: List[str]) -> Dict[str, List[List[str]]]:
    """Parses the preamble lines"""

    preamble_instructions = defaultdict(list)
    for line in preamble_lines:
        try:
            instr, *operands = group_by_word(
                line, brackets=Symbols.PREAMBLE_DEFINE_BRACKETS
            )
        except ValueError as err:
            raise NetQASMSyntaxError(
                f"Could not parse preamble instruction, since: {err}"
            )
        preamble_instructions[instr].append(operands)
    _assert_valid_preamble_instructions(preamble_instructions)
    return preamble_instructions


def _assert_valid_preamble_instructions(preamble_instructions):
    preamble_assertions = {
        Symbols.PREAMBLE_NETQASM: _assert_valid_preamble_instr_netqasm,
        Symbols.PREAMBLE_APPID: _assert_valid_preamble_instr_appid,
        Symbols.PREAMBLE_DEFINE: _assert_valid_preamble_instr_define,
    }
    for instr, list_of_operands in preamble_instructions.items():
        preamble_assertion = preamble_assertions.get(instr)
        if preamble_assertion is None:
            raise NetQASMInstrError(
                f"The instruction {instr} is not a valid preamble instruction"
            )
        preamble_assertion(list_of_operands)


def _assert_valid_preamble_instr_netqasm(list_of_operands):
    _assert_single_preamble_instr(list_of_operands, Symbols.PREAMBLE_NETQASM)
    _assert_single_preamble_arg(list_of_operands, Symbols.PREAMBLE_NETQASM)


def _assert_valid_preamble_instr_appid(list_of_operands):
    _assert_single_preamble_instr(list_of_operands, Symbols.PREAMBLE_APPID)
    _assert_single_preamble_arg(list_of_operands, Symbols.PREAMBLE_APPID)


def _assert_valid_preamble_instr_define(list_of_operands):
    macro_keys = []
    for operands in list_of_operands:
        if len(operands) != 2:
            raise NetQASMSyntaxError(
                f"Preamble instruction {Symbols.PREAMBLE_DEFINE} should contain "
                "exactly two argument, "
                f"not {len(operands)} as in '{operands}'"
            )
        macro_key, macro_value = operands
        if not is_variable_name(macro_key):
            raise NetQASMInstrError(f"{macro_key} is not a valid macro key")
        macro_keys.append(macro_key)
    if len(set(macro_keys)) < len(macro_keys):
        raise NetQASMInstrError(f"Macro keys need to be unique, not {macro_keys}")


def _assert_single_preamble_instr(list_of_operands, instr):
    if len(list_of_operands) != 1:
        raise NetQASMInstrError(
            f"Preamble should contain exactly one f{instr} instruction"
        )


def _assert_single_preamble_arg(list_of_operands, instr):
    for operands in list_of_operands:
        if len(operands) != 1:
            raise NetQASMSyntaxError(
                f"Preamble instruction {instr} should contain exactly one argument, "
                f"not {len(operands)} as in '{operands}'"
            )


def _assign_branch_labels(subroutine):
    """Finds assigns the branch labels in a subroutine (inplace)"""
    branch_labels = {}
    command_number = 0
    commands = subroutine.commands
    while command_number < len(commands):
        command = commands[command_number]
        if not isinstance(command, BranchLabel):
            command_number += 1
            continue
        branch_label = command.name
        if branch_label in branch_labels:
            raise NetQASMSyntaxError(
                f"branch labels need to be unique, name {branch_label} already used"
            )
        # Assign the label to the line/command number
        branch_labels[branch_label] = command_number
        # Remove the line
        commands = commands[:command_number] + commands[command_number + 1 :]
    subroutine.commands = commands
    _update_labels(subroutine, branch_labels)


def _update_labels(subroutine, variables: Dict[str, int], from_command=0):
    """Updates labels in a subroutine with given values"""
    for command in subroutine.commands[from_command:]:
        if isinstance(command, ICmd):
            _update_labels_in_command(command, variables)


def _update_labels_in_command(command, variables: Dict[str, int]):
    for i, operand in enumerate(command.operands):
        new_operand = _update_labels_in_operand(operand, variables)
        command.operands[i] = new_operand


def _update_labels_in_operand(operand, labels: Dict[str, int]):
    if isinstance(operand, Label):
        for label, value in labels.items():
            if operand.name == label:
                return value
    return operand


def _get_unused_address(current_addresses):
    for address in count(0):
        if address not in current_addresses:
            return address


def _make_args_operands(subroutine):
    for command in subroutine.commands:
        if not isinstance(command, ICmd):
            continue
        command.operands = command.args + command.operands
        command.args = []


_REPLACE_CONSTANTS_EXCEPTION = [
    (GenericInstr.SET, 1),
    (GenericInstr.JMP, 0),
    (GenericInstr.BEZ, 1),
    (GenericInstr.BNZ, 1),
    (GenericInstr.BEQ, 2),
    (GenericInstr.BNE, 2),
    (GenericInstr.BLT, 2),
    (GenericInstr.BGE, 2),
    (GenericInstr.BREAKPOINT, 0),
    (GenericInstr.BREAKPOINT, 1),
]

for instr in [GenericInstr.ROT_X, GenericInstr.ROT_Y, GenericInstr.ROT_Z]:
    for index in [1, 2]:
        _REPLACE_CONSTANTS_EXCEPTION.append((instr, index))

for instr in [
    GenericInstr.CROT_X,
    GenericInstr.CROT_Y,
    GenericInstr.CROT_Z,
]:
    for index in [2, 3]:
        _REPLACE_CONSTANTS_EXCEPTION.append((instr, index))


def _replace_constants(commands: List[Union[ICmd, BranchLabel]]):
    current_registers = get_current_registers(commands)

    def reg_and_set_cmd(value, tmp_registers: List[Register], lineno=None):
        for i in range(2 ** REG_INDEX_BITS):
            register = Register(RegisterName.R, i)
            if str(register) not in current_registers and register not in tmp_registers:
                break
        else:
            raise RuntimeError("Could not replace constant since no registers left")
        set_command = ICmd(
            instruction=GenericInstr.SET,
            args=[],
            operands=[register, value],
            lineno=lineno,
        )
        tmp_registers.append(register)

        return register, set_command

    i = 0
    while i < len(commands):
        command = commands[i]
        if not isinstance(command, ICmd):
            i += 1
            continue
        tmp_registers: List[Register] = []
        for j, operand in enumerate(command.operands):
            if (
                isinstance(operand, int)
                and (command.instruction, j) not in _REPLACE_CONSTANTS_EXCEPTION
            ):
                register, set_command = reg_and_set_cmd(
                    operand, tmp_registers, lineno=command.lineno
                )
                commands.insert(i, set_command)
                command.operands[j] = register

                i += 1
            else:
                if isinstance(operand, ArrayEntry):
                    attrs = ["index"]
                elif isinstance(operand, ArraySlice):
                    attrs = ["start", "stop"]
                else:
                    continue
                for attr in attrs:
                    value = getattr(operand, attr)
                    if isinstance(value, int):
                        register, set_command = reg_and_set_cmd(
                            value, tmp_registers, lineno=command.lineno
                        )
                        commands.insert(i, set_command)
                        setattr(operand, attr, register)

                        i += 1
        i += 1
    return commands


def get_current_registers(commands: List[T_Cmd]) -> Set[str]:
    current_registers = set()
    for command in commands:
        if not isinstance(command, ICmd):
            continue
        for op in command.operands:
            if isinstance(op, Register):
                current_registers.add(str(op))
    return current_registers
