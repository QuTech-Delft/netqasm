from dataclasses import dataclass
from typing import Dict

# from instr import (
#     NetQASMInstruction,
#     SingleQubitInstruction,
#     TwoQubitInstruction,
#     RotationInstruction,
# )
from netqasm.oop.instr import InstrMap, get_core_map

import netqasm.oop.instr as core

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
class GateSInstruction(core.SingleQubitInstruction):
    id: int = 24
    mnemonic: str = "s"

@dataclass
class GateKInstruction(core.SingleQubitInstruction):
    id: int = 25
    mnemonic: str = "k"

@dataclass
class GateTInstruction(core.SingleQubitInstruction):
    id: int = 26
    mnemonic: str = "t"

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
class CphaseInstruction(core.TwoQubitInstruction):
    id: int = 31
    mnemonic: str = "cphase"


def get_vanilla_map() -> InstrMap:
    core_map = get_core_map()
    id_map = core_map.id_map
    id_map.update({
        20: GateXInstruction,
        21: GateYInstruction,
        22: GateZInstruction,
        23: GateHInstruction,
        24: GateSInstruction,
        25: GateKInstruction,
        26: GateTInstruction,
        27: RotXInstruction,
        28: RotYInstruction,
        29: RotZInstruction,
        30: CnotInstruction,
        31: CphaseInstruction
    })

    name_map = core_map.name_map
    name_map.update({
        'x': GateXInstruction,
        'y': GateYInstruction,
        'z': GateZInstruction,
        'h': GateHInstruction,
        's': GateSInstruction,
        'k': GateKInstruction,
        't': GateTInstruction,
        'rot_x': RotXInstruction,
        'rot_y': RotYInstruction,
        'rot_z': RotZInstruction,
        'cnot': CnotInstruction,
        'cphase': CphaseInstruction
    })

    return InstrMap(id_map=id_map, name_map=name_map)