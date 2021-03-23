from dataclasses import dataclass

import numpy as np

from netqasm.util.quantum_gates import get_rotation_matrix

from . import core

# Explicit instruction types in the Vanilla flavour.


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
class GateSInstruction(core.SingleQubitInstruction):
    id: int = 24
    mnemonic: str = "s"

    def to_matrix(self) -> np.ndarray:
        return np.array([[1, 0], [0, 1j]])


@dataclass
class GateKInstruction(core.SingleQubitInstruction):
    id: int = 25
    mnemonic: str = "k"

    def to_matrix(self) -> np.ndarray:
        Y = GateYInstruction().to_matrix()
        Z = GateZInstruction().to_matrix()
        return (Y + Z) / np.sqrt(2)


@dataclass
class GateTInstruction(core.SingleQubitInstruction):
    id: int = 26
    mnemonic: str = "t"

    def to_matrix(self) -> np.ndarray:
        return np.array([[1, 0], [0, (1 + 1j) / np.sqrt(2)]])


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
class CnotInstruction(core.TwoQubitInstruction):
    id: int = 30
    mnemonic: str = "cnot"

    def to_matrix(self) -> np.ndarray:
        return np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]])

    def to_matrix_target_only(self) -> np.ndarray:
        return np.array([[0, 1], [1, 0]])


@dataclass
class CphaseInstruction(core.TwoQubitInstruction):
    id: int = 31
    mnemonic: str = "cphase"

    def to_matrix(self) -> np.ndarray:
        return np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, -1]])

    def to_matrix_target_only(self) -> np.ndarray:
        return np.array([[1, 0], [0, -1]])


@dataclass
class MovInstruction(core.TwoQubitInstruction):
    """Move source qubit to target qubit (target is overwritten)"""

    id: int = 41
    mnemonic: str = "mov"

    def to_matrix(self) -> np.ndarray:
        # NOTE: Currently this is represented as a full SWAP.
        return np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])

    def to_matrix_target_only(self) -> np.ndarray:  # type: ignore
        # NOTE: The mov instruction is not meant to be viewed as control-target gate.
        # Therefore, it is OK to not explicitly define a matrix.
        return None
