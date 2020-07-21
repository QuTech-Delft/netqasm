import abc
from typing import List, Set, Dict

from netqasm.subroutine import Subroutine
from netqasm.instructions import core, vanilla, nv
from netqasm.instructions.operand import Register, RegisterName, Immediate


class SubroutineCompiler(abc.ABC):
    @abc.abstractmethod
    def compile(self, subroutine):
        """Compile a subroutine (inplace) to a specific hardware

        Parameters
        ----------
        subroutine : :class:`netqasm.subroutine.Subroutine`
            The subroutine to compile
        """
        pass


class NVSubroutineCompiler(SubroutineCompiler):
    def __init__(self, subroutine: Subroutine):
        self._subroutine = subroutine
        self._used_registers: Set[Register] = set()
        self._register_values: Dict[Register, Immediate] = dict()

    def get_reg_value(self, reg: Register) -> Immediate:
        return self._register_values[reg]

    def get_unused_register(self) -> Register:
        for i in range(7, -1, -1):
            reg = Register(RegisterName.Q, i)
            if reg not in self._used_registers:
                return reg
        raise RuntimeError("Could not find free register")

    def swap(
        self,
        electron: Register,
        carbon: Register,
    ) -> List[core.NetQASMInstruction]:
        electron_hadamard = self._map_single_gate_electron(
            instr=vanilla.GateHInstruction(qreg=electron)
        )

        gates = []

        gates += [
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
        ]
        gates += electron_hadamard
        gates += [
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.RotZInstruction(qreg=carbon, angle_num=Immediate(3), angle_denom=Immediate(1)),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.RotZInstruction(qreg=carbon, angle_num=Immediate(1), angle_denom=Immediate(1)),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
        ]
        gates += electron_hadamard
        gates += [
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
        ]
        return gates

    def compile(self):
        new_commands = []

        for instr in self._subroutine.commands:
            if isinstance(instr, core.SetInstruction):
                self._register_values[instr.reg] = instr.value

            for op in instr.operands:
                if isinstance(op, Register):
                    self._used_registers.update([op])

            if (isinstance(instr, core.SingleQubitInstruction)
                    or isinstance(instr, core.RotationInstruction)):
                new_commands += self._handle_single_qubit_gate(instr)
            elif isinstance(instr, core.TwoQubitInstruction):
                new_commands += self._handle_two_qubit_gate(instr)
            else:
                new_commands += [instr]

        self._subroutine.commands = new_commands
        return self._subroutine

    def _handle_two_qubit_gate(
        self,
        instr: core.TwoQubitInstruction
    ) -> List[core.NetQASMInstruction]:
        qubit_id0 = self.get_reg_value(instr.qreg0).value
        qubit_id1 = self.get_reg_value(instr.qreg1).value
        assert qubit_id0 != qubit_id1

        if isinstance(instr, vanilla.CnotInstruction):
            if qubit_id0 == 0:
                return self._map_cnot_electron_carbon(instr)
            elif qubit_id1 == 0:
                return self._map_cnot_carbon_electron(instr)
            else:
                return self._map_cnot_carbon_carbon(instr)
        elif isinstance(instr, vanilla.CphaseInstruction):
            if qubit_id0 == 0:
                return self._map_cphase_electron_carbon(instr)
            elif qubit_id1 == 0:
                swapped = vanilla.CphaseInstruction(
                    qreg0=instr.qreg1,
                    qreg1=instr.qreg0
                )
                return self._map_cphase_electron_carbon(swapped)
            else:
                return self._map_cphase_carbon_carbon(instr)
        else:
            raise ValueError(f"Don't know how to map instruction {instr} of type {type(instr)}")

    def _map_cphase_electron_carbon(
        self,
        instr: vanilla.CphaseInstruction,
    ) -> List[core.NetQASMInstruction]:
        electron = instr.qreg0
        carbon = instr.qreg1

        return [
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.RotZInstruction(qreg=carbon, angle_num=Immediate(3), angle_denom=Immediate(1)),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.RotZInstruction(qreg=carbon, angle_num=Immediate(1), angle_denom=Immediate(1)),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
        ]

    def _map_cphase_carbon_carbon(
        self,
        instr: vanilla.CphaseInstruction
    ) -> List[core.NetQASMInstruction]:
        electron = self.get_unused_register()
        carbon = instr.qreg0
        set_electron = core.SetInstruction(reg=electron, value=Immediate(0))
        instr.qreg0 = electron
        return (
            [set_electron]
            + self.swap(electron, carbon)
            + self._map_cphase_electron_carbon(instr)
            + self.swap(electron, carbon)
        )

    def _map_cnot_electron_carbon(
        self,
        instr: vanilla.CnotInstruction,
    ) -> List[core.NetQASMInstruction]:
        electron = instr.qreg0
        carbon = instr.qreg1

        return [
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon)
        ]

    def _map_cnot_carbon_electron(
        self,
        instr: vanilla.CnotInstruction,
    ) -> List[core.NetQASMInstruction]:
        electron = instr.qreg0
        carbon = instr.qreg1

        electron_hadamard = self._map_single_gate_electron(
            instr=vanilla.GateHInstruction(qreg=electron)
        )

        gates = []
        gates += electron_hadamard
        gates += [
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.RotZInstruction(qreg=carbon, angle_num=Immediate(3), angle_denom=Immediate(1)),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.RotZInstruction(qreg=carbon, angle_num=Immediate(1), angle_denom=Immediate(1)),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
        ]
        gates += electron_hadamard

        return gates

    def _map_cnot_carbon_carbon(
        self,
        instr: vanilla.CnotInstruction
    ) -> List[core.NetQASMInstruction]:
        electron = self.get_unused_register()
        carbon = instr.qreg0
        set_electron = core.SetInstruction(reg=electron, value=Immediate(0))
        instr.qreg0 = electron
        return (
            [set_electron]
            + self.swap(electron, carbon)
            + self._map_cnot_electron_carbon(instr)
            + self.swap(electron, carbon)
        )

    def _handle_single_qubit_gate(
        self,
        instr: core.SingleQubitInstruction
    ) -> List[core.NetQASMInstruction]:
        if (isinstance(instr, core.QAllocInstruction)
                or isinstance(instr, core.QFreeInstruction)
                or isinstance(instr, core.InitInstruction)):
            return [instr]

        qubit_id = self.get_reg_value(instr.qreg).value
        if qubit_id == 0:  # electron
            return self._map_single_gate_electron(instr)
        else:  # carbon
            return self._map_single_gate_carbon(instr)

    def _map_single_gate_electron(
        self,
        instr: core.SingleQubitInstruction
    ) -> List[core.NetQASMInstruction]:
        if isinstance(instr, vanilla.GateXInstruction):
            return [
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(0))
            ]
        elif isinstance(instr, vanilla.GateYInstruction):
            return [
                nv.RotYInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(0))
            ]
        elif isinstance(instr, vanilla.GateZInstruction):
            return [
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(3), angle_denom=Immediate(1)),
                nv.RotYInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(0)),
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(1))
            ]
        elif isinstance(instr, vanilla.GateHInstruction):
            return [
                nv.RotYInstruction(
                    qreg=instr.qreg, angle_num=Immediate(3), angle_denom=Immediate(1)),
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(0)),
            ]
        elif isinstance(instr, vanilla.GateKInstruction):
            return [
                nv.RotYInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(1)),
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(0)),
            ]
        elif isinstance(instr, vanilla.GateSInstruction):
            return [
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(3), angle_denom=Immediate(1)),
                nv.RotYInstruction(
                    qreg=instr.qreg, angle_num=Immediate(3), angle_denom=Immediate(1)),
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(1))
            ]
        elif isinstance(instr, vanilla.GateTInstruction):
            return [
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(3), angle_denom=Immediate(1)),
                nv.RotYInstruction(
                    qreg=instr.qreg, angle_num=Immediate(7), angle_denom=Immediate(2)),
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(1))
            ]
        elif isinstance(instr, vanilla.RotZInstruction):
            return [
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(3), angle_denom=Immediate(1)),
                nv.RotYInstruction(
                    qreg=instr.qreg, angle_num=instr.angle_num, angle_denom=instr.angle_denom),
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(1))
            ]
        elif isinstance(instr, vanilla.RotXInstruction):
            return [
                nv.RotXInstruction(
                    qreg=instr.qreg, angle_num=instr.angle_num, angle_denom=instr.angle_denom)
            ]
        elif isinstance(instr, vanilla.RotYInstruction):
            return [
                nv.RotYInstruction(
                    qreg=instr.qreg, angle_num=instr.angle_num, angle_denom=instr.angle_denom)
            ]
        else:
            raise ValueError(f"Don't know how to map instruction {instr} of type {type(instr)}")

    def _map_single_gate_carbon(
        self,
        instr: core.SingleQubitInstruction
    ) -> List[core.NetQASMInstruction]:
        if isinstance(instr, vanilla.RotZInstruction):
            return [
                nv.RotZInstruction(
                    qreg=instr.qreg, angle_num=instr.angle_num, angle_denom=instr.angle_denom)
            ]
        elif isinstance(instr, vanilla.GateZInstruction):
            return [
                nv.RotZInstruction(
                    qreg=instr.qreg, angle_num=Immediate(1), angle_denom=Immediate(0))
            ]
        else:
            electron = self.get_unused_register()
            carbon = instr.qreg
            set_electron = core.SetInstruction(reg=electron, value=Immediate(0))
            instr.qreg = electron
            return (
                [set_electron]
                + self.swap(electron, carbon)
                + self._map_single_gate_electron(instr)
                + self.swap(electron, carbon)
            )
