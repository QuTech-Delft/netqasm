from dataclasses import dataclass

import numpy as np

from netqasm.util.quantum_gates import (
    get_controlled_rotation_matrix,
    get_rotation_matrix,
)

from . import core

# Explicit instruction types in the NV flavour.


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
class ControlledRotXInstruction(core.ControlledRotationInstruction):
    id: int = 30
    mnemonic: str = "crot_x"

    def to_matrix(self) -> np.ndarray:
        axis = [1, 0, 0]
        angle = self.angle_num.value * np.pi / 2**self.angle_denom.value
        return get_controlled_rotation_matrix(axis, angle)

    def to_matrix_target_only(self) -> np.ndarray:
        axis = [1, 0, 0]
        angle = self.angle_num.value * np.pi / 2**self.angle_denom.value
        return get_rotation_matrix(axis, angle)


@dataclass
class ControlledRotYInstruction(core.ControlledRotationInstruction):
    id: int = 31
    mnemonic: str = "crot_y"

    def to_matrix(self) -> np.ndarray:
        axis = [1, 0, 0]
        angle = self.angle_num.value * np.pi / 2**self.angle_denom.value
        return get_controlled_rotation_matrix(axis, angle)

    def to_matrix_target_only(self) -> np.ndarray:
        axis = [1, 0, 0]
        angle = self.angle_num.value * np.pi / 2**self.angle_denom.value
        return get_rotation_matrix(axis, angle)


@dataclass
class MovInstruction(core.TwoQubitInstruction):
    """Move source qubit to target qubit (target is overwritten)"""

    id: int = 51
    mnemonic: str = "mov"

    def to_matrix(self) -> np.ndarray:
        # NOTE: Currently this is represented as a full SWAP.
        return np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])

    def to_matrix_target_only(self) -> np.ndarray:  # type: ignore
        # NOTE: The mov instruction is not meant to be viewed as control-target gate.
        # Therefore, it is OK to not explicitly define a matrix.
        return None  # type: ignore


@dataclass
class SwpInstruction(core.TwoQubitInstruction):
    """Swap the states of two qubits"""

    id: int = 52
    mnemonic: str = "swp"

    def to_matrix(self) -> np.ndarray:
        return np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])

    def to_matrix_target_only(self) -> np.ndarray:  # type: ignore
        # NOTE: The swp instruction is not meant to be viewed as control-target gate.
        # Therefore, it is OK to not explicitly define a matrix.
        return None  # type: ignore
