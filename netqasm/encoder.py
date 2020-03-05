from enum import Enum, auto


class Instruction(Enum):
    QALLOC = auto()
    INIT = auto()
    STORE = auto()
    ARRAY = auto()
    ADD = auto()
    H = auto()
    X = auto()
    CNOT = auto()
    MEAS = auto()
    CREATE_EPR = auto()
    RECV_EPR = auto()
    BEQ = auto()
    WAIT = auto()
    QFREE = auto()


_INSTRUCTION_TO_STRING = {
    Instruction.QALLOC: "qalloc",
    Instruction.INIT: "init",
    Instruction.STORE: "store",
    Instruction.ARRAY: "array",
    Instruction.ADD: "add",
    Instruction.H: "h",
    Instruction.X: "x",
    Instruction.CNOT: "cnot",
    Instruction.MEAS: "meas",
    Instruction.CREATE_EPR: "create_epr",
    Instruction.RECV_EPR: "recv_epr",
    Instruction.BEQ: "beq",
    Instruction.WAIT: "wait",
    Instruction.QFREE: "qfree",
}


def instruction_to_string(instr):
    instr_str = _INSTRUCTION_TO_STRING.get(instr)
    if instr_str is None:
        raise ValueError(f"Unknown instruction {instr}")
    return instr_str


_STRING_TO_INSTRUCTION = {instr_str: instr for instr, instr_str in _INSTRUCTION_TO_STRING.items()}


def string_to_instruction(instr_str):
    instr = _STRING_TO_INSTRUCTION.get(instr_str)
    if instr is None:
        raise ValueError(f"Unknown instruction {instr_str}")
    return instr


class Encoder:
    def __init__(self):
        raise NotImplementedError
