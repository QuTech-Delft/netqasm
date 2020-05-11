import abc
import numpy as np

from netqasm.subroutine import Command, Float
from netqasm.instructions import (
    Instruction,
    STATIC_SINGLE_QUBIT_GATES,
    SINGLE_QUBIT_ROTATIONS,
    TWO_QUBIT_GATES,
)


class SubroutineCompiler(abc.ABC):
    @abc.abstractmethod
    def compile(self, subroutine):
        """Compile a subroutine to a specific hardware

        Parameters
        ----------
        subroutine : :class:`netqasm.subroutine.Subroutine`
            The subroutine to compile

        Returns
        -------
        :class:`netqasm.subroutine.Subroutine`
            The compiled subroutine
        """
        pass


class NVSubroutineCompiler(SubroutineCompiler):

    SINGLE_QUBIT_GATE_MAPPING = {
        # gate: rotation, angle
        Instruction.X: [(Instruction.ROT_X, np.pi)],
        Instruction.Y: [(Instruction.ROT_Y, np.pi)],
        Instruction.Z: [
            (Instruction.ROT_X, -np.pi / 2),
            (Instruction.ROT_Y, np.pi),
            (Instruction.ROT_X, np.pi / 2),
        ],
        Instruction.H: [
            (Instruction.ROT_Y, -np.pi / 2),
            (Instruction.ROT_X, np.pi),
        ],
        Instruction.K: [
            (Instruction.ROT_X, np.pi / 2),
            (Instruction.ROT_Y, np.pi),
        ],
        Instruction.S: [(Instruction.ROT_Z, np.pi / 2)],
        Instruction.T: [(Instruction.ROT_Z, np.pi / 4)],
    }

    def compile(self, subroutine):
        for i, command in enumerate(subroutine.command):
            if command.instruction in STATIC_SINGLE_QUBIT_GATES:
                new_commands = self._handle_single_qubit_static_gate(command)
            elif command.instruction in SINGLE_QUBIT_ROTATIONS:
                new_commands = self._handle_single_qubit_rotations(command)
            elif command.instruction in TWO_QUBIT_GATES:
                new_commands = self._handle_two_qubit_gate(command)
            else:
                # No need to do anything for classical operations
                new_commands = [command]
            subroutine.commands = subroutine.command[:i] + new_commands + subroutine.command[i + 1:]
            i += len(new_commands)

    def _handle_single_qubit_static_gate(self, command):
        qubit = command.operands[0]
        rotations = self.SINGLE_QUBIT_GATE_MAPPING[command.instruction]
        return [
            Command(instruction=rot_instr, operands=[qubit, Float(angle)])
            for rot_instr, angle in rotations
        ]

    def _handle_single_qubit_rotations(self, command):
        # We only need to handle Z-rotations
        if command.instruction == Instruction.ROT_Z:
            qubit = command.operands[0]
            angle = command.operands[1]
            return [
                Command(Instruction.ROT_X, operands=[qubit, Float(-np.pi / 2)]),
                Command(Instruction.ROT_Y, operands=[qubit, angle]),
                Command(Instruction.ROT_X, operands=[qubit, Float(np.pi / 2)]),
            ]
        elif command.instruction in [Instruction.ROT_X, Instruction.ROT_Y]:
            return [command]
        else:
            raise ValueError(f"Unknown rotation instruction {command.instruction}")

    def _handle_two_qubit_gate(self, command):
        if command.instruction == Instruction.CNOT:
            return [command]
        elif command.instruction == Instruction.CPHASE:
            target = command.operands[1]
            hadamard_gates = self._handle_single_qubit_static_gate(Command(
                instruction=Instruction.H,
                operands=[target],
            ))
            cnot_gate = Command(Instruction.CNOT, operands=list(command.operands))
            return hadamard_gates + [cnot_gate] + hadamard_gates
        else:
            raise ValueError(f"Unknown two qubit instruction {command.instruction}")


import pytest
from netqasm.parsing import parse_text_subroutine
from netqasm.quantum_gates import gate_to_matrix, are_matrices_equal


@pytest.mark.parametrize(
    'abstract_gate, nv_gates',
    NVSubroutineCompiler.SINGLE_QUBIT_GATE_MAPPING.items(),
)
def test_mapping(abstract_gate, nv_gates):
    abstract_matrix = gate_to_matrix(abstract_gate)
    nv_matrix = gate_to_matrix(*nv_gates[0])
    for nv_gate in nv_gates[1:]:
        nv_matrix = nv_matrix @ gate_to_matrix(*nv_gate)
    print(f'abstract_matrix = {abstract_matrix}')
    print(f'nv_matrix = {nv_matrix}')
    assert are_matrices_equal(abstract_matrix, nv_matrix)
    # assert are_matrices_equal(np.zeros((2, 2)), np.zeros((3, 3)))
    # assert False
    # assert np.all(np.isclose(abstract_matrix, nv_matrix))


# def test():
#     text_subroutine = """
# # NETQASM 0.0.0
# # APPID 0
# set Q0 0
# QALLOC Q0
# INIT Q0
# X Q0
# Y Q0
# Z Q0
# H Q0
# K Q0
# S Q0
# T Q0
# """
#     subroutine = parse_text_subroutine(text_subroutine)
#     new_subroutine = NVSubroutineCompiler.compile(subroutine)
#     print(new_subroutine)
