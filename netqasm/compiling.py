import abc

from netqasm.subroutine import Command
from netqasm.instructions import (
    Instruction,
    STATIC_SINGLE_QUBIT_GATES,
    SINGLE_QUBIT_ROTATION_GATES,
    TWO_QUBIT_GATES,
)


class SubroutineCompiler(abc.ABC):
    @abc.abstractclassmethod
    def compile(cls, subroutine):
        """Compile a subroutine (inplace) to a specific hardware

        Parameters
        ----------
        subroutine : :class:`netqasm.subroutine.Subroutine`
            The subroutine to compile
        """
        pass


class NVSubroutineCompiler(SubroutineCompiler):

    SINGLE_QUBIT_GATE_MAPPING = {
        # gate: rotation, angle
        Instruction.X: [(Instruction.ROT_X, (1, 1))],  # pi
        Instruction.Y: [(Instruction.ROT_Y, (1, 1))],  # pi
        Instruction.Z: [
            (Instruction.ROT_X, (3, 2)),  # - pi / 2
            (Instruction.ROT_Y, (1, 1)),  # pi
            (Instruction.ROT_X, (1, 2)),  # pi / 2
        ],
        Instruction.H: [
            (Instruction.ROT_Y, (3, 2)),  # - pi / 2
            (Instruction.ROT_X, (1, 1)),  # pi
        ],
        Instruction.K: [
            (Instruction.ROT_X, (1, 2)),  # pi / 2
            (Instruction.ROT_Y, (1, 1)),  # pi
        ],
        Instruction.S: [
            (Instruction.ROT_X, (3, 2)),  # - pi / 2
            (Instruction.ROT_Y, (3, 2)),  # - pi / 2
            (Instruction.ROT_X, (1, 2)),  # pi / 2
        ],
        Instruction.T: [
            (Instruction.ROT_X, (3, 2)),  # - pi / 2
            (Instruction.ROT_Y, (7, 4)),  # - pi / 4
            (Instruction.ROT_X, (1, 2)),  # pi / 2
        ],
    }

    @classmethod
    def compile(cls, subroutine):
        i = 0
        while i < len(subroutine.commands):
            command = subroutine.commands[i]
            if command.instruction in STATIC_SINGLE_QUBIT_GATES:
                new_commands = cls._handle_single_qubit_static_gate(command)
            elif command.instruction in SINGLE_QUBIT_ROTATION_GATES:
                new_commands = cls._handle_single_qubit_rotations(command)
            elif command.instruction in TWO_QUBIT_GATES:
                new_commands = cls._handle_two_qubit_gate(command)
            else:
                # No need to do anything for classical operations
                new_commands = [command]
            subroutine.commands = subroutine.commands[:i] + new_commands + subroutine.commands[i + 1:]
            i += len(new_commands)
            print(new_commands)
            print(i)
            print(subroutine)

    @classmethod
    def _handle_single_qubit_static_gate(cls, command):
        qubit = command.operands[0]
        rotations = cls.SINGLE_QUBIT_GATE_MAPPING[command.instruction]
        return [
            Command(instruction=rot_instr, operands=[qubit, n, d])
            for rot_instr, (n, d) in rotations
        ]

    @classmethod
    def _handle_single_qubit_rotations(cls, command):
        # We only need to handle Z-rotations
        if command.instruction == Instruction.ROT_Z:
            qubit = command.operands[0]
            n = command.operands[1]
            d = command.operands[2]
            return [
                Command(Instruction.ROT_X, operands=[qubit, 3, 2]),  # 3 pi / 2
                Command(Instruction.ROT_Y, operands=[qubit, 2 * d - n, d]),  # - n pi / d
                Command(Instruction.ROT_X, operands=[qubit, 1, 2]),  # pi / 2
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
