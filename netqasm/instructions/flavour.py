from dataclasses import dataclass
from typing import Dict, List

from netqasm.instructions import vanilla, core, nv


@dataclass
class InstrMap:
    id_map: Dict[int, core.NetQASMInstruction] = None
    name_map: Dict[str, core.NetQASMInstruction] = None


CORE_INSTRUCTIONS: List[core.NetQASMInstruction] = [
    core.QAllocInstruction,
    core.InitInstruction,
    core.ArrayInstruction,
    core.SetInstruction,
    core.StoreInstruction,
    core.LoadInstruction,
    core.UndefInstruction,
    core.LeaInstruction,
    core.JmpInstruction,
    core.BezInstruction,
    core.BnzInstruction,
    core.BeqInstruction,
    core.BneInstruction,
    core.BltInstruction,
    core.BgeInstruction,
    core.AddInstruction,
    core.SubInstruction,
    core.AddmInstruction,
    core.SubmInstruction,
    core.MeasInstruction,
    core.CreateEPRInstruction,
    core.RecvEPRInstruction,
    core.WaitAllInstruction,
    core.WaitAnyInstruction,
    core.WaitSingleInstruction,
    core.QFreeInstruction,
    core.RetRegInstruction,
    core.RetArrInstruction
]


class Flavour:
    def __init__(self, flavour_specific: List[core.NetQASMInstruction]):
        self.id_map = {instr.id: instr for instr in CORE_INSTRUCTIONS}
        self.id_map.update({instr.id: instr for instr in flavour_specific})

        self.name_map = {instr.mnemonic: instr for instr in CORE_INSTRUCTIONS}
        self.name_map.update({instr.mnemonic: instr for instr in flavour_specific})

    def get_instr_by_id(self, id: int):
        return self.id_map[id]

    def get_instr_by_name(self, name: str):
        return self.name_map[name]


class VanillaFlavour(Flavour):
    instrs = [
        vanilla.GateXInstruction,
        vanilla.GateYInstruction,
        vanilla.GateZInstruction,
        vanilla.GateHInstruction,
        vanilla.GateSInstruction,
        vanilla.GateKInstruction,
        vanilla.GateTInstruction,
        vanilla.RotXInstruction,
        vanilla.RotYInstruction,
        vanilla.RotZInstruction,
        vanilla.CnotInstruction,
        vanilla.CphaseInstruction
    ]

    def __init__(self):
        super().__init__(self.instrs)


class NVFlavour(Flavour):
    instrs = [
        nv.GateXInstruction,
        nv.GateYInstruction,
        nv.GateZInstruction,
        nv.GateHInstruction,
        nv.RotXInstruction,
        nv.RotYInstruction,
        nv.RotZInstruction,
        nv.CnotInstruction,
        nv.CSqrtXInstruction
    ]

    def __init__(self):
        super().__init__(self.instrs)
