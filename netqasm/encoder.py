from enum import Enum


class Instruction(Enum):
    # Allocation
    QALLOC = "qalloc"
    # Initialization
    INIT = "init"
    STORE = "store"
    UNSET = "unset"
    ARRAY = "array"
    # Classical logic
    BEQ = "beq"
    BNE = "bne"
    BLT = "blt"
    BGE = "bge"
    # Classical operations
    ADD = "add"
    SUB = "sub"
    # Single-qubit gates
    X = "X"
    Y = "Y"
    Z = "Z"
    H = "H"
    K = "K"
    T = "T"
    # Single-qubit rotations
    ROT_X = "ROT_X"
    ROT_Y = "ROT_Y"
    ROT_Z = "ROT_Z"
    # Two-qubit gates
    CNOT = "CNOT"
    CPHASE = "CPHASE"
    # Measurement
    MEAS = "MEAS"
    # Entanglement generation
    CREATE_EPR = "CREATE_EPR"
    RECV_EPR = "RECV_EPR"
    # Waiting
    WAIT = "WAIT"
    # Deallocation
    QFREE = "QFREE"


def instruction_to_string(instr):
    if not isinstance(instr, Instruction):
        raise ValueError(f"Unknown instruction {instr}")
    return instr.value


_STRING_TO_INSTRUCTION = {instr.value: instr for instr in Instruction}


def string_to_instruction(instr_str):
    instr = _STRING_TO_INSTRUCTION.get(instr_str)
    if instr is None:
        raise ValueError(f"Unknown instruction {instr_str}")
    return instr


class Encoder:
    def __init__(self):
        raise NotImplementedError
