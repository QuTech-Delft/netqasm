from __future__ import annotations
from typing import List, Union, Optional, Dict, Tuple
from typing import TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum, auto

from qlink_interface import (
    EPRType,
    RandomBasis,
    LinkLayerCreate,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerOKTypeR,
)


class IrInstrType(Enum):
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

    # Move source qubit to target qubit (target is overwritten)
    MOV = auto()

    PARAM = auto()  # param x
    CALL = auto()  # call x, n

    ASSIGN = auto()  # x = y
    NEW_ARRAY = auto()  # x = array y
    NEW_QUBIT = auto()  # init q

    Q_ROT_X = auto()  # q, t
    Q_ROT_Y = auto()  # q, t
    Q_ROT_Z = auto()  # q, t

    Q_X = auto()  # q
    Q_Y = auto()  # q
    Q_Z = auto()  # q
    Q_H = auto()  # q
    Q_S = auto()  # q

    Q_CNOT = auto()  # q1, q2
    Q_CPHASE = auto()  # q1, q2
    Q_MS = auto()  # q1, q2

    Q_MEAS = auto()  # q, m
    Q_FREE = auto()  # q

    Q_EPR_CK = auto()  # s, n


class IrRotAxis:
    """A rotation axis in the Bloch sphere"""

    def __init__(self, name: str) -> None:
        self._name = name


class IrSingleGate:
    """A single-qubit gate"""

    def __init__(self, name: str) -> None:
        self._name = name


class IrTwoGate:
    """A two-qubit gate"""

    def __init__(self, name: str) -> None:
        self._name = name


class IrReg:
    """A register variable"""
    _COUNT: int = 0

    def __init__(self):
        self.id: int = self.__class__._COUNT
        self.__class__._COUNT += 1


class IrArr:
    """An array variable"""
    _COUNT: int = 0

    def __init__(self):
        self.id: int = self.__class__._COUNT
        self.__class__._COUNT += 1


class IrQbt:
    """A qubit variable"""
    _COUNT: int = 0

    def __init__(self):
        self.id: int = self.__class__._COUNT
        self.__class__._COUNT += 1


class IrBlk:
    """A basic block"""
    _COUNT: int = 0

    def __init__(self):
        self.id: int = self.__class__._COUNT
        self.__class__._COUNT += 1


class IrFun:
    """A function"""
    _COUNT: int = 0

    def __init__(self, args: Dict[str, T_IrType]):
        self.id: int = self.__class__._COUNT
        self.__class__._COUNT += 1

        self._args: Dict[str, T_IrType] = args


IrImm = int
T_IrType = Union[IrReg, IrArr, IrQbt, IrImm]
T_IrOperand = Union[IrReg, IrArr, IrQbt, IrImm]


class IrRemote:
    """A remote party"""

    def __init__(self, name: str):
        self._name = name


class IrEprSocket:
    """An EPR socket"""

    def __init__(self, id: int, remote: str, rmt_id: int):
        self._id = id
        self._remote = remote
        self._rmt_id = rmt_id


@dataclass
class IrEprMeasConfig:
    """Configuration of Measure-Directly EPR generation requests"""

    random_basis_local: Optional[RandomBasis] = None,
    random_basis_remote: Optional[RandomBasis] = None,
    rotations_local: Tuple[int, int, int] = (0, 0, 0),
    rotations_remote: Tuple[int, int, int] = (0, 0, 0),


class IrInstr:
    def __init__(
        self,
        typ: IrInstrType,
        operands: List[T_IrOperand],
        parent: Optional[IrBlk] = None,
    ):
        self._typ: IrInstrType = typ
        self._operands: List[T_IrOperand] = operands
        self._parent: Optional[IrBlk] = parent
