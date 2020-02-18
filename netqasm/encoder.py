from enum import Enum, auto


class Instruction(Enum):
    CREG = auto()
    QREG = auto()
    OUTPUT = auto()  # Other name?

    INIT = auto()

    ADD = auto()

    H = auto()
    X = auto()
    MEAS = auto()

    BEQ = auto()

    CFREE = auto()
    QFREE = auto()


_INSTRUCTION_TO_STRING = {
    Instruction.QREG: "qreg",
    Instruction.CREG: "creg",
    Instruction.OUTPUT: "output",
    Instruction.INIT: "init",
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


class Encoder:
    def __init__(self):
        raise NotImplementedError
