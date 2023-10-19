from dataclasses import dataclass
from typing import List, Union

import numpy as np

from netqasm.lang.operand import Immediate, Operand, Register, Template
from netqasm.util.quantum_gates import get_rotation_matrix

from . import base, core


@dataclass  # type: ignore
class AllQubitsRotationInstruction(base.ImmImmInstruction):
    @property
    def angle_num(self):
        return self.imm0

    @angle_num.setter
    def angle_num(self, new_val: Immediate):
        self.imm0 = new_val

    @property
    def angle_denom(self):
        return self.imm1

    @angle_denom.setter
    def angle_denom(self, new_val: Immediate):
        self.imm1 = new_val

    @classmethod
    def from_operands(cls, operands: List[Union[Operand, int]]):
        assert len(operands) == 2
        imm0, imm1 = operands

        if isinstance(imm0, int):
            imm0 = Immediate(value=imm0)
        elif isinstance(imm0, Immediate):
            pass
        else:
            assert isinstance(imm0, Template) or isinstance(imm0, Register)
        if isinstance(imm1, int):
            imm1 = Immediate(value=imm1)
        elif isinstance(imm1, Immediate):
            pass
        else:
            assert isinstance(imm1, Template) or isinstance(imm1, Register)
        # We allow imm0, imm1 to be Templates OR registers
        return cls(imm0=imm0, imm1=imm1)  # type: ignore


@dataclass
class AllQubitsInitInstruction(base.NoOperandInstruction):
    id: int = 42
    mnemonic: str = "init_all"


@dataclass
class AllQubitsMeasInstruction(base.RegAddrInstruction):
    id: int = 43
    mnemonic: str = "meas_all"


@dataclass
class RotZInstruction(core.RotationInstruction):
    id: int = 29
    mnemonic: str = "rot_z"

    def to_matrix(self) -> np.ndarray:
        axis = [0, 0, 1]
        angle = self.angle_num.value * np.pi / 2**self.angle_denom.value
        return get_rotation_matrix(axis, angle)


@dataclass
class AllQubitsRotXInstruction(AllQubitsRotationInstruction):
    id: int = 44
    mnemonic: str = "rot_x_all"


@dataclass
class AllQubitsRotYInstruction(AllQubitsRotationInstruction):
    id: int = 45
    mnemonic: str = "rot_y_all"


@dataclass
class AllQubitsRotZInstruction(AllQubitsRotationInstruction):
    id: int = 46
    mnemonic: str = "rot_z_all"


@dataclass
class BichromaticInstruction(base.ImmImmInstruction):
    id: int = 47
    mnemonic: str = "bichromatic"

    @property
    def angle_num(self):
        return self.imm0

    @angle_num.setter
    def angle_num(self, new_val: Immediate):
        self.imm0 = new_val

    @property
    def angle_denom(self):
        return self.imm1

    @angle_denom.setter
    def angle_denom(self, new_val: Immediate):
        self.imm1 = new_val

    @classmethod
    def from_operands(cls, operands: List[Union[Operand, int]]):
        assert len(operands) == 2
        imm0, imm1 = operands

        if isinstance(imm0, int):
            imm0 = Immediate(value=imm0)
        elif isinstance(imm0, Immediate):
            pass
        else:
            assert isinstance(imm0, Template) or isinstance(imm0, Register)
        if isinstance(imm1, int):
            imm1 = Immediate(value=imm1)
        elif isinstance(imm1, Immediate):
            pass
        else:
            assert isinstance(imm1, Template) or isinstance(imm1, Register)
        # We allow imm0, imm1 to be Templates OR registers
        return cls(imm0=imm0, imm1=imm1)  # type: ignore
