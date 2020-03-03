from enum import Enum, auto


class Instruction(Enum):
    QALLOC = auto()
    INIT = auto()
    STORE = auto()
    ARRAY = auto()
    ADD = auto()
    H = auto()
    X = auto()
    MEAS = auto()
    BEQ = auto()
    CFREE = auto()
    QFREE = auto()


_INSTRUCTION_TO_STRING = {
    Instruction.QALLOC: "qalloc",
    Instruction.INIT: "init",
    Instruction.STORE: "store",
    Instruction.ARRAY: "array",
    Instruction.ADD: "add",
    Instruction.H: "h",
    Instruction.X: "x",
    Instruction.MEAS: "meas",
    Instruction.BEQ: "beq",
    Instruction.CFREE: "cfree",
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
