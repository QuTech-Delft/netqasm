"""Transpilation of subroutines from one flavour to another.

This module contains the SubroutineCompiler interface which is a base class for
transpilers that can convert a NetQASM subroutine into a subroutine with a specific
flavour.
"""

import abc
from typing import Dict, List, Optional, Set, Tuple, Union

from netqasm.lang.instr import DebugInstruction, NetQASMInstruction, core, nv, vanilla
from netqasm.lang.operand import Immediate, Register, RegisterName
from netqasm.lang.subroutine import Subroutine
from netqasm.runtime.settings import get_is_using_hardware
from netqasm.util.log import HostLine


class SubroutineCompiler(abc.ABC):
    def __init__(self, subroutine: Subroutine, debug: bool = False):
        pass

    @abc.abstractmethod
    def compile(self) -> Subroutine:
        """Compile the subroutine into one with a specific flavour."""
        pass


class NVSubroutineCompiler(SubroutineCompiler):
    """A transpiler that converts a subroutine with the vanilla flavour to a subroutine
    with the NV flavour.
    """

    def __init__(self, subroutine: Subroutine, debug=False):
        self._subroutine: Subroutine = subroutine
        self._used_registers: Set[Register] = set()
        self._register_values: Dict[Register, Immediate] = dict()
        self._debug: bool = debug

    def get_reg_value(self, reg: Register) -> Immediate:
        """Get the value of a register at this moment"""
        return self._register_values[reg]

    def get_unused_register(self) -> Register:
        """
        Naive approach: try to use Q0 if possible, otherwise Q1, etc.
        """
        for i in range(16):
            reg = Register(RegisterName.Q, i)
            if reg not in self._used_registers:
                return reg
        raise RuntimeError("Could not find free register")

    def swap(
        self,
        lineno: Optional[HostLine],
        electron: Register,
        carbon: Register,
    ) -> List[NetQASMInstruction]:
        """
        Swap the states of the electron and a carbon.
        See https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-docs/-/blob/master/nv-gates-docs.md
        for the circuit.
        """
        gates: List[NetQASMInstruction] = []

        if self._debug:
            gates += [DebugInstruction(text="begin SWAP")]

        gates += [
            nv.ControlledRotXInstruction(
                lineno=lineno,
                reg0=electron,
                reg1=carbon,
                imm0=Immediate(8),
                imm1=Immediate(4),
            ),
            nv.RotXInstruction(
                lineno=lineno, reg=electron, imm0=Immediate(24), imm1=Immediate(4)
            ),
            nv.RotYInstruction(
                lineno=lineno, reg=electron, imm0=Immediate(16), imm1=Immediate(4)
            ),
            nv.RotZInstruction(
                lineno=lineno, reg=carbon, imm0=Immediate(24), imm1=Immediate(4)
            ),
            nv.ControlledRotXInstruction(
                lineno=lineno,
                reg0=electron,
                reg1=carbon,
                imm0=Immediate(8),
                imm1=Immediate(4),
            ),
            nv.RotXInstruction(
                lineno=lineno, reg=electron, imm0=Immediate(8), imm1=Immediate(4)
            ),
            nv.RotYInstruction(
                lineno=lineno, reg=electron, imm0=Immediate(8), imm1=Immediate(4)
            ),
            nv.RotXInstruction(
                lineno=lineno, reg=carbon, imm0=Immediate(8), imm1=Immediate(4)
            ),
            nv.RotZInstruction(
                lineno=lineno, reg=carbon, imm0=Immediate(8), imm1=Immediate(4)
            ),
            nv.ControlledRotXInstruction(
                lineno=lineno,
                reg0=electron,
                reg1=carbon,
                imm0=Immediate(8),
                imm1=Immediate(4),
            ),
            nv.RotYInstruction(
                lineno=lineno, reg=electron, imm0=Immediate(16), imm1=Immediate(4)
            ),
            nv.RotZInstruction(
                lineno=lineno, reg=carbon, imm0=Immediate(16), imm1=Immediate(4)
            ),
        ]

        if self._debug:
            gates += [DebugInstruction(text="end SWAP")]

        return gates

    def compile(self) -> Subroutine:
        """
        Very simple compiling pass: iterate over all instructions once and rewrite them in-line.
        While iterating, keep track of which registers are in use and what their values are.
        """
        new_commands: List[NetQASMInstruction] = []

        index_changes = {}  # map index in commands to index in new_commands

        for i, instr in enumerate(self._subroutine.commands):
            # check which registers are being written to
            affected_regs = instr.writes_to()

            for reg in affected_regs:
                if reg.name != RegisterName.Q:
                    continue  # for now we are only interested in Q-register values

                if isinstance(instr, core.SetInstruction):
                    # OK, value is a known Immediate. Update register value:
                    self._register_values[reg] = instr.imm
                else:
                    pass
                    # don't allow writing to a Q-register by any other instruction type
                    # TODO
                    # raise RuntimeError(
                    #     f"Cannot compile: the instruction {instr} writes to"
                    #     " a Q-register but the value cannot be determined"
                    #     " at compile time.")

            for op in instr.operands:
                # update used registers
                if isinstance(op, Register):
                    self._used_registers.update([op])

            index_changes[i] = len(new_commands)

            if isinstance(instr, core.SingleQubitInstruction) or isinstance(
                instr, core.RotationInstruction
            ):
                new_commands += self._handle_single_qubit_gate(instr)
            elif isinstance(instr, core.TwoQubitInstruction):
                new_commands += self._handle_two_qubit_gate(instr)
            else:
                new_commands += [instr]

        add_no_op_at_end = False

        for instr in new_commands:
            if (
                isinstance(instr, core.BranchUnaryInstruction)
                or isinstance(instr, core.BranchBinaryInstruction)
                or isinstance(instr, core.JmpInstruction)
            ):
                original_line = instr.line.value
                if original_line == len(self._subroutine.commands):
                    # There was a label in the original subroutine at the very end.
                    # Since this label is now removed, we should put a "no-op"
                    # instruction there so there is something to jump to.
                    add_no_op_at_end = True
                    instr.line = Immediate(len(new_commands))
                else:
                    instr.line = Immediate(index_changes[instr.line.value])

        if add_no_op_at_end:
            new_commands += [
                core.SetInstruction(
                    lineno=None, reg=Register(RegisterName.C, 15), imm=Immediate(1337)
                )
            ]

        self._subroutine.commands = new_commands
        return self._subroutine

    def _move_electron_carbon(
        self, instr: vanilla.MovInstruction
    ) -> List[NetQASMInstruction]:
        """
        See https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-docs/-/blob/master/nv-gates-docs.md
        for the circuit.
        """
        electron = instr.reg0
        carbon = instr.reg1
        return [
            nv.RotYInstruction(
                lineno=instr.lineno, reg=electron, imm0=Immediate(8), imm1=Immediate(4)
            ),
            nv.ControlledRotYInstruction(
                lineno=instr.lineno,
                reg0=electron,
                reg1=carbon,
                imm0=Immediate(24),
                imm1=Immediate(4),
            ),
            nv.RotXInstruction(
                lineno=instr.lineno, reg=electron, imm0=Immediate(24), imm1=Immediate(4)
            ),
            nv.ControlledRotXInstruction(
                lineno=instr.lineno,
                reg0=electron,
                reg1=carbon,
                imm0=Immediate(8),
                imm1=Immediate(4),
            ),
        ]

    def _move_carbon_electron(
        self, instr: vanilla.MovInstruction
    ) -> List[NetQASMInstruction]:
        """
        See https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-docs/-/blob/master/nv-gates-docs.md
        for the circuit.
        """
        electron = instr.reg1
        carbon = instr.reg0
        return [
            nv.RotYInstruction(
                lineno=instr.lineno, reg=electron, imm0=Immediate(8), imm1=Immediate(4)
            ),
            nv.ControlledRotYInstruction(
                lineno=instr.lineno,
                reg0=electron,
                reg1=carbon,
                imm0=Immediate(24),
                imm1=Immediate(4),
            ),
            nv.RotXInstruction(
                lineno=instr.lineno, reg=electron, imm0=Immediate(24), imm1=Immediate(4)
            ),
            nv.ControlledRotXInstruction(
                lineno=instr.lineno,
                reg0=electron,
                reg1=carbon,
                imm0=Immediate(8),
                imm1=Immediate(4),
            ),
            nv.RotYInstruction(
                lineno=instr.lineno, reg=electron, imm0=Immediate(24), imm1=Immediate(4)
            ),
            nv.RotZInstruction(
                lineno=instr.lineno, reg=electron, imm0=Immediate(24), imm1=Immediate(4)
            ),
        ]

    def _handle_two_qubit_gate(
        self, instr: core.TwoQubitInstruction
    ) -> List[NetQASMInstruction]:
        try:
            qubit_id0 = self.get_reg_value(instr.reg0).value
            qubit_id1 = self.get_reg_value(instr.reg1).value
        except KeyError:
            # Register values are not known at compile time.
            # We may assume that this is a MOV operation from the communication
            # qubit to a memory qubit. (This is the only time a gate uses
            # operands that are not known at compile time.)
            assert isinstance(instr, vanilla.MovInstruction)
            return self._move_electron_carbon(instr)

        assert qubit_id0 != qubit_id1

        # It is assumed that there is only one electron, and that its virtual ID is 0.
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
                    lineno=instr.lineno, reg0=instr.reg1, reg1=instr.reg0
                )
                return self._map_cphase_electron_carbon(swapped)
            else:
                return self._map_cphase_carbon_carbon(instr)
        elif isinstance(instr, vanilla.MovInstruction):
            if qubit_id0 == 0 and qubit_id1 != 0:
                return self._move_electron_carbon(instr)
            elif qubit_id0 != 0 and qubit_id1 == 0:
                return self._move_carbon_electron(instr)
            else:
                raise RuntimeError(f"Cannot move qubit {qubit_id0} to {qubit_id1}")
        else:
            raise ValueError(
                f"Don't know how to map instruction {instr} of type {type(instr)}"
            )

    def _map_cphase_electron_carbon(
        self,
        instr: vanilla.CphaseInstruction,
    ) -> List[NetQASMInstruction]:
        electron = instr.reg0
        carbon = instr.reg1
        """
        See https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-docs/-/blob/master/nv-gates-docs.md
        for the circuit.
        """

        return [
            nv.RotYInstruction(
                lineno=instr.lineno, reg=carbon, imm0=Immediate(8), imm1=Immediate(4)
            ),
            nv.ControlledRotXInstruction(
                lineno=instr.lineno,
                reg0=electron,
                reg1=carbon,
                imm0=Immediate(8),
                imm1=Immediate(4),
            ),
            nv.RotZInstruction(
                lineno=instr.lineno, reg=electron, imm0=Immediate(24), imm1=Immediate(4)
            ),
            nv.RotXInstruction(
                lineno=instr.lineno, reg=carbon, imm0=Immediate(24), imm1=Immediate(4)
            ),
            nv.RotYInstruction(
                lineno=instr.lineno, reg=carbon, imm0=Immediate(24), imm1=Immediate(4)
            ),
        ]

    def _map_cphase_carbon_carbon(
        self, instr: vanilla.CphaseInstruction
    ) -> List[NetQASMInstruction]:
        """
        See https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-docs/-/blob/master/nv-gates-docs.md
        for the circuit.
        """
        electron = self.get_unused_register()
        carbon = instr.reg0
        set_electron = core.SetInstruction(
            lineno=instr.lineno, reg=electron, imm=Immediate(0)
        )
        instr.reg0 = electron

        result: List[NetQASMInstruction] = [set_electron]
        result += (
            self.swap(instr.lineno, electron, carbon)
            + self._map_cphase_electron_carbon(instr)
            + self.swap(instr.lineno, electron, carbon)
        )
        return result

    def _map_cnot_electron_carbon(
        self,
        instr: vanilla.CnotInstruction,
    ) -> List[NetQASMInstruction]:
        electron = instr.reg0
        carbon = instr.reg1
        """
        See https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-docs/-/blob/master/nv-gates-docs.md
        for the circuit.
        """

        return [
            nv.ControlledRotXInstruction(
                lineno=instr.lineno,
                reg0=electron,
                reg1=carbon,
                imm0=Immediate(8),
                imm1=Immediate(4),
            ),
            nv.RotZInstruction(
                lineno=instr.lineno, reg=electron, imm0=Immediate(24), imm1=Immediate(4)
            ),
            nv.RotXInstruction(
                lineno=instr.lineno, reg=carbon, imm0=Immediate(24), imm1=Immediate(4)
            ),
        ]

    def _map_cnot_carbon_electron(
        self,
        instr: vanilla.CnotInstruction,
    ) -> List[NetQASMInstruction]:
        """
        See https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-docs/-/blob/master/nv-gates-docs.md
        for the circuit.
        """
        electron = instr.reg1
        carbon = instr.reg0

        electron_hadamard = self._map_single_gate(
            instr=vanilla.GateHInstruction(lineno=instr.lineno, reg=electron)
        )

        gates = []
        gates += electron_hadamard
        gates += [
            nv.RotYInstruction(
                lineno=instr.lineno, reg=carbon, imm0=Immediate(8), imm1=Immediate(4)
            ),
            nv.ControlledRotXInstruction(
                lineno=instr.lineno,
                reg0=electron,
                reg1=carbon,
                imm0=Immediate(8),
                imm1=Immediate(4),
            ),
            nv.RotZInstruction(
                lineno=instr.lineno, reg=electron, imm0=Immediate(24), imm1=Immediate(4)
            ),
            nv.RotXInstruction(
                lineno=instr.lineno, reg=carbon, imm0=Immediate(24), imm1=Immediate(4)
            ),
            nv.RotYInstruction(
                lineno=instr.lineno, reg=carbon, imm0=Immediate(24), imm1=Immediate(4)
            ),
        ]
        gates += electron_hadamard

        return gates

    def _map_cnot_carbon_carbon(
        self, instr: vanilla.CnotInstruction
    ) -> List[NetQASMInstruction]:
        """
        See https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-docs/-/blob/master/nv-gates-docs.md
        for the circuit.
        """
        electron = self.get_unused_register()
        carbon = instr.reg0
        set_electron = core.SetInstruction(
            lineno=instr.lineno, reg=electron, imm=Immediate(0)
        )
        instr.reg0 = electron

        result: List[NetQASMInstruction] = [set_electron]
        result += (
            self.swap(instr.lineno, electron, carbon)
            + self._map_cnot_electron_carbon(instr)
            + self.swap(instr.lineno, electron, carbon)
        )
        return result

    def _handle_single_qubit_gate(
        self,
        instr: Union[core.SingleQubitInstruction, core.RotationInstruction],
    ) -> List[NetQASMInstruction]:
        return self._map_single_gate(instr)

    def _map_single_gate(
        self,
        instr: Union[core.SingleQubitInstruction, core.RotationInstruction],
    ) -> List[NetQASMInstruction]:
        if isinstance(instr, vanilla.GateXInstruction):
            return [
                nv.RotXInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(16),
                    imm1=Immediate(4),
                )
            ]
        elif isinstance(instr, vanilla.GateYInstruction):
            return [
                nv.RotYInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(16),
                    imm1=Immediate(4),
                )
            ]
        elif isinstance(instr, vanilla.GateZInstruction):
            return [
                nv.RotXInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(24),
                    imm1=Immediate(4),
                ),
                nv.RotYInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(16),
                    imm1=Immediate(4),
                ),
                nv.RotXInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(8),
                    imm1=Immediate(4),
                ),
            ]
        elif isinstance(instr, vanilla.GateHInstruction):
            return [
                nv.RotYInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(8),
                    imm1=Immediate(4),
                ),
                nv.RotXInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(16),
                    imm1=Immediate(4),
                ),
            ]
        elif isinstance(instr, vanilla.GateKInstruction):
            return [
                nv.RotXInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(24),
                    imm1=Immediate(4),
                ),
                nv.RotYInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(16),
                    imm1=Immediate(4),
                ),
            ]
        elif isinstance(instr, vanilla.GateSInstruction):
            return [
                nv.RotXInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(24),
                    imm1=Immediate(4),
                ),
                nv.RotYInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(24),
                    imm1=Immediate(4),
                ),
                nv.RotXInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(8),
                    imm1=Immediate(4),
                ),
            ]
        elif isinstance(instr, vanilla.GateTInstruction):
            return [
                nv.RotXInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(24),
                    imm1=Immediate(4),
                ),
                nv.RotYInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(28),
                    imm1=Immediate(4),
                ),
                nv.RotXInstruction(
                    lineno=instr.lineno,
                    reg=instr.reg,
                    imm0=Immediate(8),
                    imm1=Immediate(4),
                ),
            ]
        elif isinstance(instr, vanilla.RotZInstruction):
            if get_is_using_hardware():
                imm0, imm1 = get_hardware_num_denom(instr)
            else:
                imm0, imm1 = instr.angle_num, instr.angle_denom
            return [
                nv.RotZInstruction(
                    lineno=instr.lineno, reg=instr.reg, imm0=imm0, imm1=imm1
                ),
            ]
        elif isinstance(instr, vanilla.RotXInstruction):
            if get_is_using_hardware():
                imm0, imm1 = get_hardware_num_denom(instr)
            else:
                imm0, imm1 = instr.angle_num, instr.angle_denom
            return [
                nv.RotXInstruction(
                    lineno=instr.lineno, reg=instr.reg, imm0=imm0, imm1=imm1
                ),
            ]
        elif isinstance(instr, vanilla.RotYInstruction):
            if get_is_using_hardware():
                imm0, imm1 = get_hardware_num_denom(instr)
            else:
                imm0, imm1 = instr.angle_num, instr.angle_denom
            return [
                nv.RotYInstruction(
                    lineno=instr.lineno, reg=instr.reg, imm0=imm0, imm1=imm1
                ),
            ]
        else:
            raise ValueError(
                f"Don't know how to map instruction {instr} of type {type(instr)}"
            )


def get_hardware_num_denom(
    instr: core.RotationInstruction,
) -> Tuple[Immediate, Immediate]:
    if instr.angle_denom.value not in [0, 1, 2, 3, 4]:
        raise ValueError(
            f"Instruction {instr} not supported: angle_denom is {instr.angle_denom}."
        )

    denom_diff = 4 - instr.angle_denom.value
    angle_num = instr.angle_num.value * (2 ** denom_diff)
    return (Immediate(angle_num), Immediate(4))
