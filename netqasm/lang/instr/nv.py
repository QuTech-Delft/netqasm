from dataclasses import dataclass

import numpy as np

from netqasm.util.quantum_gates import (
    get_controlled_rotation_matrix,
    get_rotation_matrix,
)

from . import core

# Explicit instruction types in the NV flavour.


@dataclass
class GateXInstruction(core.SingleQubitInstruction):
    id: int = 20
    mnemonic: str = "x"

    def to_matrix(self) -> np.ndarray:
        return np.array([[0, 1], [1, 0]])


@dataclass
class GateYInstruction(core.SingleQubitInstruction):
    id: int = 21
    mnemonic: str = "y"

    def to_matrix(self) -> np.ndarray:
        return np.array([[0, -1j], [1j, 0]])


@dataclass
class GateZInstruction(core.SingleQubitInstruction):
    id: int = 22
    mnemonic: str = "z"

    def to_matrix(self) -> np.ndarray:
        return np.array([[1, 0], [0, -1]])


@dataclass
class GateHInstruction(core.SingleQubitInstruction):
    id: int = 23
    mnemonic: str = "h"

    def to_matrix(self) -> np.ndarray:
        X = GateXInstruction().to_matrix()
        Z = GateZInstruction().to_matrix()
        return (X + Z) / np.sqrt(2)


@dataclass
class RotXInstruction(core.RotationInstruction):
    id: int = 27
    mnemonic: str = "rot_x"

    def to_matrix(self) -> np.ndarray:
        axis = [1, 0, 0]
        angle = self.angle_num.value * np.pi / 2 ** self.angle_denom.value
        return get_rotation_matrix(axis, angle)


@dataclass
class RotYInstruction(core.RotationInstruction):
    id: int = 28
    mnemonic: str = "rot_y"

    def to_matrix(self) -> np.ndarray:
        axis = [0, 1, 0]
        angle = self.angle_num.value * np.pi / 2 ** self.angle_denom.value
        return get_rotation_matrix(axis, angle)


@dataclass
class RotZInstruction(core.RotationInstruction):
    id: int = 29
    mnemonic: str = "rot_z"

    def to_matrix(self) -> np.ndarray:
        axis = [0, 0, 1]
        angle = self.angle_num.value * np.pi / 2 ** self.angle_denom.value
        return get_rotation_matrix(axis, angle)


@dataclass
class ControlledRotXInstruction(core.ControlledRotationInstruction):
    id: int = 30
    mnemonic: str = "crot_x"

    def to_matrix(self) -> np.ndarray:
        axis = [1, 0, 0]
        angle = self.angle_num.value * np.pi / 2 ** self.angle_denom.value
        return get_controlled_rotation_matrix(axis, angle)

    def to_matrix_target_only(self) -> np.ndarray:
        axis = [1, 0, 0]
        angle = self.angle_num.value * np.pi / 2 ** self.angle_denom.value
        return get_rotation_matrix(axis, angle)


@dataclass
class ControlledRotYInstruction(core.ControlledRotationInstruction):
    id: int = 31
    mnemonic: str = "crot_y"

    def to_matrix(self) -> np.ndarray:
        axis = [1, 0, 0]
        angle = self.angle_num.value * np.pi / 2 ** self.angle_denom.value
        return get_controlled_rotation_matrix(axis, angle)

    def to_matrix_target_only(self) -> np.ndarray:
        axis = [1, 0, 0]
        angle = self.angle_num.value * np.pi / 2 ** self.angle_denom.value
        return get_rotation_matrix(axis, angle)
