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


class Encoder:
    def __init__(self):
        raise NotImplementedError
