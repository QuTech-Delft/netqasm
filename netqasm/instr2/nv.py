from dataclasses import dataclass
from typing import Dict

from netqasm.instr2.core import InstrMap, get_core_map

import netqasm.instr2.core as core

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
class CSqrtXInstruction(core.TwoQubitInstruction):
    id: int = 30
    mnemonic: str = "csqx"


def get_nv_map() -> InstrMap:
    core_map = get_core_map()
    id_map = core_map.id_map
    id_map.update({
        27: RotXInstruction,
        28: RotYInstruction,
        29: RotZInstruction,
        30: CSqrtXInstruction,
    })

    name_map = core_map.name_map
    name_map.update({
        'rot_x': RotXInstruction,
        'rot_y': RotYInstruction,
        'rot_z': RotZInstruction,
        'csqx': CSqrtXInstruction,
    })

    return InstrMap(id_map=id_map, name_map=name_map)