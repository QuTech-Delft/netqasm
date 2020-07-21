from dataclasses import dataclass


import netqasm.instructions.core as core


@dataclass
class GateXInstruction(core.SingleQubitInstruction):
    id: int = 20
    mnemonic: str = "x"


@dataclass
class GateYInstruction(core.SingleQubitInstruction):
    id: int = 21
    mnemonic: str = "y"


@dataclass
class GateZInstruction(core.SingleQubitInstruction):
    id: int = 22
    mnemonic: str = "z"


@dataclass
class GateHInstruction(core.SingleQubitInstruction):
    id: int = 23
    mnemonic: str = "h"


@dataclass
class RotXInstruction(core.RotationInstruction):
    id: int = 27
    mnemonic: str = "rot_x"


@dataclass
class RotYInstruction(core.RotationInstruction):
    id: int = 28
    mnemonic: str = "rot_y"


@dataclass
class RotZInstruction(core.RotationInstruction):
    id: int = 29
    mnemonic: str = "rot_z"


@dataclass
class CnotInstruction(core.TwoQubitInstruction):
    id: int = 30
    mnemonic: str = "cnot"


@dataclass
class CSqrtXInstruction(core.TwoQubitInstruction):
    id: int = 31
    mnemonic: str = "csqx"
