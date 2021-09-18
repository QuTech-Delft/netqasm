from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Type

from . import NetQASMInstruction, core, nv, vanilla


@dataclass
class InstrMap:
    id_map: Optional[Dict[int, Type[NetQASMInstruction]]] = None
    name_map: Optional[Dict[str, Type[NetQASMInstruction]]] = None


CORE_INSTRUCTIONS: List[Type[NetQASMInstruction]] = [
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
    core.RetArrInstruction,
    core.BreakpointInstruction,
]


class Flavour(ABC):
    """
    A Flavour represents an explicit instruction set that adheres to the Core NetQASM specification.
    Typically, a flavour is used for each specific target hardware.

    A flavour 'inherits' all classical instructions from the core, but can specify explicitly
    the quantum instructions that the hardware supports, by listing the corresponding instruction classes.

    Examples of flavours are the Vanilla flavour (with instructions defined in vanilla.py)
    and the Nitrogen-Vacancy (NV) flavour (instructions in nv.py).
    """

    def __init__(self, flavour_specific: List[Type[NetQASMInstruction]]):
        self.id_map = {instr.id: instr for instr in CORE_INSTRUCTIONS}
        self.id_map.update({instr.id: instr for instr in flavour_specific})

        self.name_map = {instr.mnemonic: instr for instr in CORE_INSTRUCTIONS}
        self.name_map.update({instr.mnemonic: instr for instr in flavour_specific})

    def get_instr_by_id(self, id: int):
        return self.id_map[id]

    def get_instr_by_name(self, name: str):
        return self.name_map[name]

    @property
    @abstractmethod
    def instrs(self):
        pass


class VanillaFlavour(Flavour):
    @property
    def instrs(self):
        return [
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
            vanilla.CphaseInstruction,
            vanilla.MovInstruction,
        ]

    def __init__(self):
        super().__init__(self.instrs)


class NVFlavour(Flavour):
    @property
    def instrs(self):
        return [
            nv.RotXInstruction,
            nv.RotYInstruction,
            nv.RotZInstruction,
            nv.ControlledRotXInstruction,
            nv.ControlledRotYInstruction,
        ]

    def __init__(self):
        super().__init__(self.instrs)
