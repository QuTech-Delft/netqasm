import ctypes
from enum import Enum


class GenericInstr(Enum):
    # Allocation
    QALLOC = 1
    # Initialization
    INIT = 2
    ARRAY = 3
    SET = 4
    # Memory
    STORE = 5
    LOAD = 6
    UNDEF = 7
    LEA = 8
    # Classical logic
    JMP = 9
    BEZ = 10
    BNZ = 11
    BEQ = 12
    BNE = 13
    BLT = 14
    BGE = 15
    # Classical operations
    ADD = 16
    SUB = 17
    ADDM = 18
    SUBM = 19
    # Single-qubit gates
    X = 20
    Y = 21
    Z = 22
    H = 23
    S = 24
    K = 25
    T = 26
    # Single-qubit rotations
    ROT_X = 27
    ROT_Y = 28
    ROT_Z = 29
    # Two-qubit gates
    CNOT = 30
    CPHASE = 31
    # Measurement
    MEAS = 32
    # Entanglement generation
    CREATE_EPR = 33
    RECV_EPR = 34
    # Waiting
    WAIT_ALL = 35
    WAIT_ANY = 36
    WAIT_SINGLE = 37
    # Deallocation
    QFREE = 38
    # Return
    RET_REG = 39
    RET_ARR = 40

    # Move source qubit to target qubit (target is overwritten)
    MOV = 41

    CROT_X = 51
    CROT_Y = 52


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
