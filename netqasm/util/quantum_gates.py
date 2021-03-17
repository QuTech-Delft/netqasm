import numpy as np
from scipy import linalg

from netqasm.lang.instr.instr_enum import Instruction

# Single-qubit gates
X = np.array([[0, 1], [1, 0]])
Y = np.array([[0, -1j], [1j, 0]])
Z = np.array([[1, 0], [0, -1]])
PAULIS = [X, Y, Z]
H = (X + Z) / np.sqrt(2)
K = (Y + Z) / np.sqrt(2)
S = np.array([[1, 0], [0, 1j]])
T = np.array([[1, 0], [0, (1 + 1j) / np.sqrt(2)]])
# Two-qubit gates
CNOT = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]])
CPHASE = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, -1]])


STATIC_QUBIT_GATE_TO_MATRIX = {
    Instruction.X: X,
    Instruction.Y: Y,
    Instruction.Z: Z,
    Instruction.H: H,
    Instruction.K: K,
    Instruction.S: S,
    Instruction.T: T,
    Instruction.CNOT: CNOT,
    Instruction.CPHASE: CPHASE,
}


def get_rotation_matrix(axis, angle):
    """Returns a single-qubit rotation matrix given an axis and an angle"""
    norm = linalg.norm(axis)
    if norm == 0:
        raise ValueError("Axis need to have non-negative norm")
    axis = axis / norm
    rot_mat = linalg.expm(-1j * angle / 2 * sum(a * P for a, P in zip(axis, PAULIS)))
    return rot_mat


def get_controlled_rotation_matrix(axis, angle) -> np.array:
    target_pos = get_rotation_matrix(axis, angle)
    target_neg = get_rotation_matrix(axis, -angle)

    ctrl_zero = np.array([[1, 0], [0, 0]])
    ctrl_one = np.array([[0, 0], [0, 1]])

    inv_controlled_gate = np.kron(ctrl_zero, target_pos) + np.kron(ctrl_one, np.eye(2))
    controlled_gate = np.kron(ctrl_one, target_neg) + np.kron(ctrl_zero, np.eye(2))

    return inv_controlled_gate @ controlled_gate


def gate_to_matrix(instr, angle=None):
    """Returns the matrix representation of a quantum gate"""
    if instr in STATIC_QUBIT_GATE_TO_MATRIX:
        return STATIC_QUBIT_GATE_TO_MATRIX[instr]
    elif instr in [Instruction.ROT_X, Instruction.ROT_Y, Instruction.ROT_Z]:
        if angle is None:
            raise TypeError('To get the matrix of a rotation an angle needs to be specified')
        axis = {
            Instruction.ROT_X: [1, 0, 0],
            Instruction.ROT_Y: [0, 1, 0],
            Instruction.ROT_Z: [0, 0, 1],
        }[instr]
        if isinstance(angle, tuple):
            n, d = angle
            angle = n * np.pi / 2 ** d
        return get_rotation_matrix(axis=axis, angle=angle)
    else:
        raise ValueError(f"{instr} is not a quantum gate")


def are_matrices_equal(*matrices):
    """Checks if two matrices are equal, disregarding any global phase"""
    if len(matrices) <= 1:
        return True
    # Get the first non zero entry of the first matrix
    non_zero_indices = np.nonzero(matrices[0])
    # Check if all entries are zero
    if len(non_zero_indices[0]) == 0:
        # All other matrices should also be zero
        for matrix in matrices[1:]:
            if not np.allclose(matrix, 0):
                return False
        return True
    first_non_zero = non_zero_indices[0][0], non_zero_indices[1][0]
    # Check equality against the rest of the matrices
    for matrix in matrices[1:]:
        # If another matrix has zero at this place, it is not equal
        if matrix[first_non_zero] == 0:
            return False
        # Check what phase to apply to the matrix so that it is the same as the first
        phase = np.angle(matrices[0][first_non_zero] / matrix[first_non_zero])
        if not np.allclose(matrices[0], np.exp(phase * 1j) * matrix):
            return False
    return True
