from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

from netqasm.lang.symbols import Symbols
from netqasm.lang.version import NETQASM_VERSION
from netqasm.util.string import rspaces

if TYPE_CHECKING:
    from netqasm.util import log

from netqasm.lang.operand import Label, Operand, Template

T_ProtoOperand = Union[int, Label, Operand]


class GenericInstr(Enum):
    # Allocation
    QALLOC = auto()
    # Initialization
    INIT = auto()
    ARRAY = auto()
    SET = auto()
    # Memory
    STORE = auto()
    LOAD = auto()
    UNDEF = auto()
    LEA = auto()
    # Classical logic
    JMP = auto()
    BEZ = auto()
    BNZ = auto()
    BEQ = auto()
    BNE = auto()
    BLT = auto()
    BGE = auto()
    # Classical operations
    ADD = auto()
    SUB = auto()
    ADDM = auto()
    SUBM = auto()
    # Single-qubit gates
    X = auto()
    Y = auto()
    Z = auto()
    H = auto()
    S = auto()
    K = auto()
    T = auto()
    # Single-qubit rotations
    ROT_X = auto()
    ROT_Y = auto()
    ROT_Z = auto()
    # Two-qubit gates
    CNOT = auto()
    CPHASE = auto()
    # Measurement
    MEAS = auto()
    MEAS_BASIS = auto()
    # Entanglement generation
    CREATE_EPR = auto()
    RECV_EPR = auto()
    # Waiting
    WAIT_ALL = auto()
    WAIT_ANY = auto()
    WAIT_SINGLE = auto()
    # Deallocation
    QFREE = auto()
    # Return
    RET_REG = auto()
    RET_ARR = auto()

    CROT_X = auto()
    CROT_Y = auto()
    CROT_Z = auto()

    # Move source qubit to target qubit (target is overwritten)
    MOV = auto()

    # Breakpoint
    BREAKPOINT = auto()


class BreakpointAction(Enum):
    NOP = 0
    DUMP_LOCAL_STATE = 1
    DUMP_GLOBAL_STATE = 2


class BreakpointRole(Enum):
    CREATE = 0
    RECEIVE = 1


def instruction_to_string(instr):
    if not isinstance(instr, GenericInstr):
        raise ValueError(f"Unknown instruction {instr}")
    return instr.name.lower()


def flip_branch_instr(instr: GenericInstr) -> GenericInstr:
    try:
        return {
            GenericInstr.BEQ: GenericInstr.BNE,
            GenericInstr.BNE: GenericInstr.BEQ,
            GenericInstr.BLT: GenericInstr.BGE,
            GenericInstr.BGE: GenericInstr.BLT,
            GenericInstr.BEZ: GenericInstr.BNZ,
            GenericInstr.BNZ: GenericInstr.BEZ,
        }[instr]
    except KeyError:
        raise ValueError(f"Not a branch instruction {instr}")


_STRING_TO_INSTRUCTION = {instruction_to_string(instr): instr for instr in GenericInstr}


def string_to_instruction(instr_str):
    instr = _STRING_TO_INSTRUCTION.get(instr_str)
    if instr is None:
        raise ValueError(f"Unknown instruction {instr_str}")
    return instr


def _get_lineo_str(lineno):
    if lineno is None:
        lineno = "()"
    else:
        lineno = f"({lineno})"
    return f"{rspaces(lineno, min_chars=5)} "


@dataclass
class ICmd:
    instruction: GenericInstr
    args: List[int] = None  # type: ignore
    operands: List[T_ProtoOperand] = None  # type: ignore
    lineno: Optional[log.HostLine] = None

    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.operands is None:
            self.operands = []

    def __str__(self):
        return self._build_str(show_lineno=False)

    @property
    def debug_str(self):
        return self._build_str(show_lineno=True)

    def _build_str(self, show_lineno=False):
        if len(self.args) == 0:
            args = ""
        else:
            args = Symbols.ARGS_DELIM.join(str(arg) for arg in self.args)
            args = Symbols.ARGS_BRACKETS[0] + args + Symbols.ARGS_BRACKETS[1]
        operands = " ".join(str(operand) for operand in self.operands)
        instr_name = instruction_to_string(self.instruction)
        if show_lineno:
            lineno_str = _get_lineo_str(self.lineno)
        else:
            lineno_str = ""
        return f"{lineno_str}{instr_name}{args} {operands}"


@dataclass
class BranchLabel:
    name: str
    lineno: Optional[log.HostLine] = None

    def _assert_types(self):
        assert isinstance(self.name, str)

    def __str__(self):
        return self._build_str(show_lineno=False)

    @property
    def debug_str(self):
        return self._build_str(show_lineno=True)

    def _build_str(self, show_lineno=False):
        if show_lineno:
            lineno_str = _get_lineo_str(self.lineno)
        else:
            lineno_str = ""
        return f"{lineno_str}{self.name}{Symbols.BRANCH_END}"


class ProtoSubroutine:
    """
    A `ProtoSubroutine` object represents a preliminary subroutine that consists
    of general 'commands' that might not yet be valid NetQASM instructions.
    These commands can include labels, or instructions with immediates that
    still need to be converted to registers.

    ProtoSubroutines can optionally have *arguments*, which are
    yet-to-be-defined variables that are used in one or more of the commands in
    the ProtoSubroutine. So, a ProtoSubroutine can be seen as a function which
    takes certain parameters (arguments). Concrete values for arguments can be
    given by instantiating (using the `instantiate` method).

    `ProtoSubroutine`s are currently only used by the sdk and the text parser
    (netqasm.parser.text). In both cases they are converted into `Subroutine`
    objects before given to other package components.
    """

    def __init__(
        self,
        commands: Optional[List[Union[ICmd, BranchLabel]]] = None,
        arguments: Optional[List[str]] = None,
        netqasm_version: Tuple[int, int] = NETQASM_VERSION,
        app_id: Optional[int] = None,
    ) -> None:
        self._netqasm_version: Tuple[int, int] = netqasm_version
        self._app_id: Optional[int] = app_id

        self._commands: List[Union[ICmd, BranchLabel]] = []
        if commands is not None:
            self.commands = commands

        self._arguments: List[str] = []
        if arguments is not None:
            self._arguments = arguments

        else:
            # figure out arguments by inspecting all commands
            for cmd in self.commands:
                if not isinstance(cmd, ICmd):
                    continue
                for op in cmd.operands:
                    if isinstance(op, Template):
                        self._arguments.append(op.name)

    @property
    def netqasm_version(self) -> Tuple[int, int]:
        return self._netqasm_version

    @property
    def app_id(self) -> Optional[int]:
        return self._app_id

    @property
    def commands(self) -> List[Union[ICmd, BranchLabel]]:
        return self._commands

    @commands.setter
    def commands(self, new_commands: List[Union[ICmd, BranchLabel]]) -> None:
        self._commands = new_commands

    @property
    def arguments(self) -> List[str]:
        return self._arguments

    def __str__(self):
        result = "ProtoSubroutine"

        if len(self.arguments) > 0:
            result += "(" + ",".join(arg_name for arg_name in self.arguments) + ")"
        result += "\n"
        result += f"  NetQASM version: {self.netqasm_version}\n"
        result += f"  App ID: {self.app_id}\n"

        result += " LN | HLN | CMD\n"
        for i, command in enumerate(self.commands):
            result += f"{rspaces(i)} {command.debug_str}\n"
        return result

    def instantiate(self, app_id: int, arguments: Dict[str, int]) -> None:
        commands: List[Union[ICmd, BranchLabel]] = []
        for cmd in self.commands:
            if not isinstance(cmd, ICmd):
                continue
            ops: List[T_ProtoOperand] = []
            for op in cmd.operands:
                if isinstance(op, Template):
                    ops.append(arguments[op.name])
                else:
                    ops.append(op)
            cmd.operands = ops
            commands.append(cmd)

        self.commands = commands
        self._app_id = app_id
