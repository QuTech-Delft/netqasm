import abc
from typing import List, Set, Dict, Union

from netqasm.subroutine import Command
from netqasm.instructions import (
    Instruction,
    STATIC_SINGLE_QUBIT_GATES,
    SINGLE_QUBIT_ROTATION_GATES,
    TWO_QUBIT_GATES,
)

from netqasm.subroutine import Subroutine
from netqasm.instr2.core import NetQASMInstruction
from netqasm.instr2 import core, vanilla, nv
from netqasm.instr2.flavour import Flavour, VanillaFlavour, NVFlavour
from netqasm.instr2.operand import Register, RegisterName, Immediate


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

    @abc.abstractmethod
    def map_instr(self, instr: NetQASMInstruction) -> List[NetQASMInstruction]:
        pass


class NVSubroutineCompiler(SubroutineCompiler):

    SINGLE_QUBIT_GATE_MAPPING = {
        # gate: rotation, angle
        Instruction.X: [(Instruction.ROT_X, (1, 0))],  # pi
        Instruction.Y: [(Instruction.ROT_Y, (1, 0))],  # pi
        Instruction.Z: [
            (Instruction.ROT_X, (3, 1)),  # - pi / 2
            (Instruction.ROT_Y, (1, 0)),  # pi
            (Instruction.ROT_X, (1, 1)),  # pi / 2
        ],
        Instruction.H: [
            (Instruction.ROT_Y, (3, 1)),  # - pi / 2
            (Instruction.ROT_X, (1, 0)),  # pi
        ],
        Instruction.K: [
            (Instruction.ROT_X, (1, 1)),  # pi / 2
            (Instruction.ROT_Y, (1, 0)),  # pi
        ],
        Instruction.S: [
            (Instruction.ROT_X, (3, 1)),  # - pi / 2
            (Instruction.ROT_Y, (3, 1)),  # - pi / 2
            (Instruction.ROT_X, (1, 1)),  # pi / 2
        ],
        Instruction.T: [
            (Instruction.ROT_X, (3, 1)),  # - pi / 2
            (Instruction.ROT_Y, (7, 2)),  # - pi / 4
            (Instruction.ROT_X, (1, 1)),  # pi / 2
        ],
    }

    def __init__(self, subroutine: Subroutine):
        self._subroutine = subroutine
        self._used_registers: Set[Register] = set()
        self._register_values: Dict[Register, Immediate] = dict()

    def get_reg_value(self, reg: Register) -> Immediate:
        return self._register_values[reg]
        # for i in range(instr_index - 1, -1, -1):
        #     instr = self._subroutine.commands[i]
        #     if isinstance(instr, core.SetInstruction):
        #         if instr.reg == reg:
        #             return instr.value
        # raise RuntimeError(f"No assignment to register {reg} found in previous commands")

    # def get_unused_register(self, instrs: List[core.NetQASMInstruction]) -> Register:
    def get_unused_register(self) -> Register:
        for i in range(7, -1, -1):
            reg = Register(RegisterName.Q, i)
            if reg not in self._used_registers:
                return reg
            # in_use = False
            # for instr in instrs:
            #     if reg in instr.operands:
            #         in_use = True
            #         break
            # if not in_use:
            #     return reg
        raise RuntimeError("Could not find free register")

    def swap(
        self,
        electron: Register,
        carbon: Register,
    ) -> List[core.NetQASMInstruction]:
        electron_hadamard = self._map_single_gate_electron(
            instr=vanilla.GateHInstruction(qreg=electron)
        )

        return ([
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
        ] + electron_hadamard
          + [
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.RotZInstruction(qreg=carbon, angle_num=Immediate(3), angle_denom=Immediate(1)),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.RotZInstruction(qreg=carbon, angle_num=Immediate(1), angle_denom=Immediate(1)),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
        ] + electron_hadamard
        + [
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
            nv.CSqrtXInstruction(qreg0=electron, qreg1=carbon),
        ])

    def swap_and_do_instr_on_electron(
        self,
        # carbon_id,
        carbon: Register,
        instr: Union[core.SingleQubitInstruction, core.RotationInstruction]
    ) -> List[core.NetQASMInstruction]:
        electron = self.get_unused_register()
        set_electron = core.SetInstruction(reg=electron, value=Immediate(0))

        # self._used_registers.update([electron])

        # carbon = self.get_unused_register()
        # set_carbon = core.SetInstruction(reg=carbon, value=Immediate(carbon_id))

        # self._used_registers.remove(electron)

        # return ([set_electron, set_carbon]
        instr.qreg = electron
        return ([set_electron]
            + self.swap(electron, carbon)
            + self._map_single_gate_electron(instr)
            + self.swap(electron, carbon)
        )

    def map_instr(self, instr: NetQASMInstruction) -> List[NetQASMInstruction]:
        if isinstance(instr, vanilla.GateXInstruction):
            reg = instr.qreg
            print(f"reg = {reg}")
            qubit_id = self.get_reg_value(reg).value
            print(f"qubit_id = {qubit_id}")
            if qubit_id == 0:
                print(f"X Gate on electron, OK")
            else:
                print(f"X Gate on carbon, inserting SWAP with electron")
                # return self.swap_and_do_gate_on_electron(
                #     carbon_id=qubit_id,
                #     gate=instr.__class__
                # )
                
        return [instr]

    def compile(self):
        i = 0

        new_commands = []

        # while i < len(subroutine.commands):
        #     command = subroutine.commands[i]
        #     if command.instruction in STATIC_SINGLE_QUBIT_GATES:
        #         new_commands = cls._handle_single_qubit_static_gate(command)
        #     elif command.instruction in SINGLE_QUBIT_ROTATION_GATES:
        #         new_commands = cls._handle_single_qubit_rotations(command)
        #     elif command.instruction in TWO_QUBIT_GATES:
        #         new_commands = cls._handle_two_qubit_gate(command)
        #     else:
        #         # No need to do anything for classical operations
        #         new_commands = [command]
        #     subroutine.commands = subroutine.commands[:i] + new_commands + subroutine.commands[i + 1:]
        #     i += len(new_commands)
        for instr in self._subroutine.commands:
            if isinstance(instr, core.SetInstruction):
                self._register_values[instr.reg] = instr.value

            for op in instr.operands:
                if isinstance(op, Register):
                    self._used_registers.update([op])
            
            print(f"compiling instr {instr}")

            if (isinstance(instr, core.SingleQubitInstruction)
                or isinstance(instr, core.RotationInstruction)):
                new_commands += self._handle_single_qubit_gate(instr)
            else:
                new_commands += [instr]
            
        # print(f"new_commands = {new_commands}")
        print(f"type(new_commands) = {type(new_commands)}")
        # for comm in new_commands:
        #     print(f"comm: {comm}")

        self._subroutine.commands = new_commands
        return self._subroutine

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

        # rotations = cls.SINGLE_QUBIT_GATE_MAPPING[command.instruction]
        # return [
        #     Command(instruction=rot_instr, operands=[qubit, n, d])
        #     for rot_instr, (n, d) in rotations
        # ]

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
            return self.swap_and_do_instr_on_electron(
                carbon=instr.qreg,
                instr=instr
            )


    @classmethod
    def _handle_single_qubit_rotations(cls, command):
        # We only need to handle Z-rotations
        if command.instruction == Instruction.ROT_Z:
            qubit = command.operands[0]
            n = command.operands[1]
            d = command.operands[2]
            return [
                Command(Instruction.ROT_X, operands=[qubit, 3, 1]),  # 3 pi / 2
                Command(Instruction.ROT_Y, operands=[qubit, 2 * 2 ** d - n, d]),  # - n pi / 2 ^ d
                Command(Instruction.ROT_X, operands=[qubit, 1, 1]),  # pi / 2
            ]
        elif command.instruction in [Instruction.ROT_X, Instruction.ROT_Y]:
            return [command]
        else:
            raise ValueError(f"Unknown rotation instruction {command.instruction}")

    @classmethod
    def _handle_two_qubit_gate(cls, command):
        # TODO below is just a simple mapping from CPHASE TO CNOT
        # However, one needs to replace CNOT between qubits which does not have
        # connectivity in the hardware with effective CNOTs using the center-qubit
        raise NotImplementedError("Compilation of two qubit gates are not yet implemented")
        if command.instruction == Instruction.CNOT:
            return [command]
        elif command.instruction == Instruction.CPHASE:
            target = command.operands[1]
            hadamard_gates = cls._handle_single_qubit_static_gate(Command(
                instruction=Instruction.H,
                operands=[target],
            ))
            cnot_gate = Command(Instruction.CNOT, operands=list(command.operands))
            return hadamard_gates + [cnot_gate] + hadamard_gates
        else:
            raise ValueError(f"Unknown two qubit instruction {command.instruction}")
