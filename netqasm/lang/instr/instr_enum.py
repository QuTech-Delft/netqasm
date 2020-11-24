from enum import Enum
from typing import Dict
import ctypes
from netqasm.lang.encoding import (
    RegCommand,
    RegRegCommand,
    MeasCommand,
    RegImmImmCommand,
    RegRegRegCommand,
    RegRegRegRegCommand,
    ImmCommand,
    RegImmCommand,
    RegRegImmCommand,
    RegEntryCommand,
    ArrayEntryCommand,
    ArraySliceCommand,
    RegAddrCommand,
    SingleRegisterCommand,
    ArrayCommand,
    AddrCommand,
    Reg5Command,
)


class Instruction(Enum):
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


_COMMAND_GROUPS = {
    RegCommand: [
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
    RegRegCommand: [
        Instruction.CNOT,
        Instruction.CPHASE,
    ],
    MeasCommand: [
        Instruction.MEAS,
    ],
    RegImmImmCommand: [
        Instruction.ROT_X,
        Instruction.ROT_Y,
        Instruction.ROT_Z,
    ],
    RegRegRegCommand: [
        Instruction.ADD,
        Instruction.SUB,
    ],
    RegRegRegRegCommand: [
        Instruction.ADDM,
        Instruction.SUBM,
        Instruction.RECV_EPR,
    ],
    ImmCommand: [
        Instruction.JMP,
    ],
    RegRegImmCommand: [
        Instruction.BEQ,
        Instruction.BNE,
        Instruction.BLT,
        Instruction.BGE,
    ],
    RegImmCommand: [
        Instruction.SET,
        Instruction.BEZ,
        Instruction.BNZ,
    ],
    RegEntryCommand: [
        Instruction.STORE,
        Instruction.LOAD,
    ],
    RegAddrCommand: [
        Instruction.LEA,
    ],
    ArrayEntryCommand: [
        Instruction.UNDEF,
        Instruction.WAIT_SINGLE,
    ],
    ArraySliceCommand: [
        Instruction.WAIT_ALL,
        Instruction.WAIT_ANY,
    ],
    SingleRegisterCommand: [
        Instruction.RET_REG,
    ],
    ArrayCommand: [
        Instruction.ARRAY,
    ],
    AddrCommand: [
        Instruction.RET_ARR,
    ],
    Reg5Command: [
        Instruction.CREATE_EPR,
    ],
}

# Quantum gates
STATIC_SINGLE_QUBIT_GATES = [
    Instruction.X,
    Instruction.Y,
    Instruction.Z,
    Instruction.H,
    Instruction.K,
    Instruction.S,
    Instruction.T,
]

SINGLE_QUBIT_ROTATION_GATES = [
    Instruction.ROT_X,
    Instruction.ROT_Y,
    Instruction.ROT_Z,
]

SINGLE_QUBIT_GATES = STATIC_SINGLE_QUBIT_GATES + SINGLE_QUBIT_ROTATION_GATES

TWO_QUBIT_GATES = [
    Instruction.CNOT,
    Instruction.CPHASE,
]

QUBIT_GATES = SINGLE_QUBIT_GATES + TWO_QUBIT_GATES

EPR_INSTR = [
    Instruction.CREATE_EPR,
    Instruction.RECV_EPR,
]


def instruction_to_string(instr):
    if not isinstance(instr, Instruction):
        raise ValueError(f"Unknown instruction {instr}")
    return instr.name.lower()


def flip_branch_instr(instr):
    try:
        return {
            Instruction.BEQ: Instruction.BNE,
            Instruction.BNE: Instruction.BEQ,
            Instruction.BLT: Instruction.BGE,
            Instruction.BGE: Instruction.BLT,
            Instruction.BEZ: Instruction.BNZ,
            Instruction.BNZ: Instruction.BEZ,
        }[instr]
    except KeyError:
        raise ValueError(f"Not a branch instruction {instr}")


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


COMMAND_STRUCTS: Dict[Instruction, ctypes.Structure] = {
    instr: _create_command_struct(instr, command_group)
    for command_group, instrs in _COMMAND_GROUPS.items()
    for instr in instrs
}
