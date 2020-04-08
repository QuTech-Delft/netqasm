from enum import Enum, auto
from netqasm.encoding import (
    SingleQubitCommand,
    TwoQubitCommand,
    MeasCommand,
    RotationCommand,
    ClassicalOpCommand,
    ClassicalOpModCommand,
    BranchCommand,
    SetCommand,
    RegisterAddressCommand,
    SingleAddressCommand,
    ArrayCommand,
    CreateEPRCommand,
    RecvEPRCommand,
)


class Instruction(Enum):
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
    # Entanglement generation
    CREATE_EPR = auto()
    RECV_EPR = auto()
    # Waiting
    WAIT = auto()
    # Deallocation
    QFREE = auto()
    # Return
    RET_REG = auto()
    RET_ARR = auto()


_COMMAND_GROUPS = {
    SingleQubitCommand: [
        Instruction.QALLOC,
        Instruction.INIT,
        Instruction.X,
        Instruction.Y,
        Instruction.Z,
        Instruction.H,
        Instruction.K,
        Instruction.T,
        Instruction.QFREE,
    ],
    TwoQubitCommand: [
        Instruction.CNOT,
        Instruction.CPHASE,
    ],
    MeasCommand: [
        Instruction.MEAS,
    ],
    RotationCommand: [
        Instruction.ROT_X,
        Instruction.ROT_Y,
        Instruction.ROT_Z,
    ],
    ClassicalOpCommand: [
        Instruction.ADD,
        Instruction.SUB,
    ],
    ClassicalOpModCommand: [
        Instruction.ADDM,
        Instruction.SUBM,
    ],
    BranchCommand: [
        Instruction.BEQ,
        Instruction.BNE,
        Instruction.BLT,
        Instruction.BGE,
    ],
    SetCommand: [
        Instruction.SET,
    ],
    RegisterAddressCommand: [
        Instruction.STORE,
        Instruction.LOAD,
        Instruction.LEA,
    ],
    SingleAddressCommand: [
        Instruction.UNDEF,
        Instruction.WAIT,
    ],
    ArrayCommand: [
        Instruction.ARRAY,
    ],
    CreateEPRCommand: [
        Instruction.CREATE_EPR,
    ],
    RecvEPRCommand: [
        Instruction.RECV_EPR,
    ],
}


def instruction_to_string(instr):
    if not isinstance(instr, Instruction):
        raise ValueError(f"Unknown instruction {instr}")
    return instr.name.lower()


_STRING_TO_INSTRUCTION = {instruction_to_string(instr): instr for instr in Instruction}


def string_to_instruction(instr_str):
    instr = _STRING_TO_INSTRUCTION.get(instr_str)
    if instr is None:
        raise ValueError(f"Unknown instruction {instr_str}")
    return instr


def _create_command_struct(instr, command_group):
    instr_name = instruction_to_string(instr)
    class_name = f"{instr_name}Command"
    class_name = class_name[0].upper() + class_name[1:]
    return type(
        class_name,
        (command_group,),
        {"ID": instr.value},
    )


COMMAND_STRUCTS = {
    instr: _create_command_struct(instr, command_group)
    for command_group, instrs in _COMMAND_GROUPS.items()
    for instr in instrs
}


# TESTING

from netqasm.encoding import Command


def test_all_commmands():
    for instr in Instruction:
        command = COMMAND_STRUCTS[instr]
        assert isinstance(command(), Command)
