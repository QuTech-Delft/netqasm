from enum import Enum, auto
from netqasm.encoding import (
    SingleQubitCommand,
    TwoQubitCommand,
    MeasCommand,
    RotationCommand,
    ClassicalOpCommand,
    ClassicalOpModCommand,
    JumpCommand,
    BranchUnaryCommand,
    BranchBinaryCommand,
    SetCommand,
    LoadStoreCommand,
    SingleArrayEntryCommand,
    SingleArraySliceCommand,
    LeaCommand,
    SingleRegisterCommand,
    ArrayCommand,
    RetArrCommand,
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


_COMMAND_GROUPS = {
    SingleQubitCommand: [
        Instruction.QALLOC,
        Instruction.INIT,
        Instruction.X,
        Instruction.Y,
        Instruction.Z,
        Instruction.H,
        Instruction.S,
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
    JumpCommand: [
        Instruction.JMP,
    ],
    BranchUnaryCommand: [
        Instruction.BEZ,
        Instruction.BNZ,
    ],
    BranchBinaryCommand: [
        Instruction.BEQ,
        Instruction.BNE,
        Instruction.BLT,
        Instruction.BGE,
    ],
    SetCommand: [
        Instruction.SET,
    ],
    LoadStoreCommand: [
        Instruction.STORE,
        Instruction.LOAD,
    ],
    LeaCommand: [
        Instruction.LEA,
    ],
    SingleArrayEntryCommand: [
        Instruction.UNDEF,
        Instruction.WAIT_SINGLE,
    ],
    SingleArraySliceCommand: [
        Instruction.WAIT_ALL,
        Instruction.WAIT_ANY,
    ],
    SingleRegisterCommand: [
        Instruction.RET_REG,
    ],
    ArrayCommand: [
        Instruction.ARRAY,
    ],
    RetArrCommand: [
        Instruction.RET_ARR,
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
