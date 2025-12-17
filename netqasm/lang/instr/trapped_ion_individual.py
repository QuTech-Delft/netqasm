from dataclasses import dataclass
from typing import List, Union

import numpy as np

from netqasm.lang.operand import Immediate, Operand, Register, Template
from netqasm.util.quantum_gates import get_rotation_matrix

from . import base, core



@dataclass
class RotXInstruction(core.RotationInstruction):
    id: int = 27
    mnemonic: str = "rot_x"

    def to_matrix(self) -> np.ndarray:
        axis = [1, 0, 0]
        angle = self.angle_num.value * np.pi / 2**self.angle_denom.value
        return get_rotation_matrix(axis, angle)


@dataclass
class RotYInstruction(core.RotationInstruction):
    id: int = 28
    mnemonic: str = "rot_y"

    def to_matrix(self) -> np.ndarray:
        axis = [0, 1, 0]
        angle = self.angle_num.value * np.pi / 2**self.angle_denom.value
        return get_rotation_matrix(axis, angle)


@dataclass
class RotZInstruction(core.RotationInstruction):
    id: int = 29
    mnemonic: str = "rot_z"

    def to_matrix(self) -> np.ndarray:
        axis = [0, 0, 1]
        angle = self.angle_num.value * np.pi / 2**self.angle_denom.value
        return get_rotation_matrix(axis, angle)


@dataclass
class MSGateInstruction(core.TwoQubitInstruction):
    id: int = 48
    mnemonic: str = "ms"

    @classmethod
    def from_operands(cls, operands: List[Union[Operand, int]]):
        raise NotImplementedError()

    def to_matrix(self):
        # TODO put implementation here
        pass

    def to_matrix_target_only(self):
        # NOTE: The MS instruction acts on both qubits
        # Therefore, it is OK to not explicitly define a matrix.
        return None  # type: ignore