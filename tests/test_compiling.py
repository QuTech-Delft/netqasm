from typing import Dict, Set

import numpy as np
import pytest

from netqasm.backend.messages import deserialize_host_msg as deserialize_message
from netqasm.lang.instr import core
from netqasm.lang.instr.flavour import NVFlavour, VanillaFlavour
from netqasm.lang.operand import Register
from netqasm.lang.parsing import deserialize as deserialize_subroutine
from netqasm.lang.parsing import parse_text_subroutine
from netqasm.lang.subroutine import Subroutine
from netqasm.logging.glob import set_log_level
from netqasm.sdk.compiling import NVSubroutineCompiler
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.qubit import Qubit


def pad_single_matrix(m: np.ndarray, index: int, total: int) -> np.ndarray:
    """Create matrix for `total` qubits where `m` is applied on qubit `index`
    and identities on the other qubits"""
    matrix = np.eye(1)
    for i in range(total):
        if i == index:
            matrix = np.kron(matrix, m)
        else:
            matrix = np.kron(matrix, np.eye(2))
    return matrix


def pad_controlled_single_matrix(
    m: np.ndarray, ctrl_index, target_index, total
) -> np.ndarray:
    """Create matrix for `total` qubits where `m` is applied on qubit `target_index`
    if qubit in `ctrl_index` is 1 (and identities on the other qubits).
    E.g. pad_controlled_single_matrix(X, 3, 1, 3) returns a 4-qubit matrix representing a CNOT
    from qubit 3 to 1, while qubits 0 and 2 are not affected (identities).
    """
    matrix0 = np.eye(1)
    for i in range(total):
        if i == ctrl_index:
            matrix0 = np.kron(matrix0, np.array([[1, 0], [0, 0]]))
        else:
            matrix0 = np.kron(matrix0, np.eye(2))

    matrix1 = np.eye(1)
    for i in range(total):
        if i == ctrl_index:
            matrix1 = np.kron(matrix1, np.array([[0, 0], [0, 1]]))
        elif i == target_index:
            matrix1 = np.kron(matrix1, m)
        else:
            matrix1 = np.kron(matrix1, np.eye(2))

    return matrix0 + matrix1


class SubroutineMatrix:
    """Matrix representing the quantum operations in a subroutine"""

    def __init__(self, virt_ids: Set[int]):
        self._virt_ids = virt_ids
        self._matrix_indices: Dict[
            int, int
        ] = dict()  # map of virt ID to index in matrix

        self._matrix = np.eye(1)
        for i, id in enumerate(virt_ids):
            self._matrix_indices[id] = i
            self._matrix = np.kron(self._matrix, np.eye(2))

    def apply_single_qubit_instr(self, instr_matrix: np.ndarray, virt_id: int):
        m = pad_single_matrix(
            m=instr_matrix,
            index=self._matrix_indices[virt_id],
            total=len(self._matrix_indices.keys()),
        )

        self._matrix = self._matrix @ m

    def apply_two_qubit_instr(
        self, instr_matrix: np.ndarray, virt_id0: int, virt_id1: int
    ):
        m = pad_controlled_single_matrix(
            m=instr_matrix,
            ctrl_index=self._matrix_indices[virt_id0],
            target_index=self._matrix_indices[virt_id1],
            total=len(self._matrix_indices.keys()),
        )

        self._matrix = self._matrix @ m

    @property
    def matrix(self):
        return self._matrix


def _subroutine_as_matrix(subroutine: Subroutine) -> np.ndarray:
    """Try to write quantum instructions in subroutine as one matrix.
    This function relies on the fact that the subroutine has only "set"
    instructions for Q registers, and should only be used for subroutines
    specifically made for testing the NV compiler.
    """
    qreg_values: Dict[Register, int] = dict()
    virt_ids: Set[int] = set()

    # first pass: collect virt IDs used
    for instr in subroutine.commands:
        if isinstance(instr, core.SetInstruction):
            virt_ids.add(instr.imm.value)

    sub_matrix = SubroutineMatrix(virt_ids)

    # second pass: keep track of qreg values and construct matrix
    for instr in subroutine.commands:
        if isinstance(instr, core.SetInstruction):
            qreg_values[instr.reg] = instr.imm.value

        if isinstance(instr, core.SingleQubitInstruction):
            sub_matrix.apply_single_qubit_instr(
                instr.to_matrix(), qreg_values[instr.reg]
            )
        elif isinstance(instr, core.RotationInstruction):
            sub_matrix.apply_single_qubit_instr(
                instr.to_matrix(), qreg_values[instr.reg]
            )
        elif isinstance(instr, core.TwoQubitInstruction):
            sub_matrix.apply_two_qubit_instr(
                instr_matrix=instr.to_matrix_target_only(),
                virt_id0=qreg_values[instr.reg0],
                virt_id1=qreg_values[instr.reg1],
            )

    return sub_matrix.matrix


@pytest.mark.parametrize(
    "text_subroutine",
    [
        (
            """
        # NETQASM 0.0
        # APPID 0
        set Q0 0
        z Q0
        """
        ),
        (
            """
        # NETQASM 0.0
        # APPID 0
        set Q0 0
        set Q1 1
        rot_x Q0 3 1
        """
        ),
        (
            """
        # NETQASM 0.0
        # APPID 0
        set Q0 0
        set Q1 1
        cnot Q1 Q0
        """
        ),
        (
            """
        # NETQASM 0.0
        # APPID 0
        set Q0 0
        set Q1 1
        cphase Q1 Q0
        """
        ),
        (
            """
        # NETQASM 0.0
        # APPID 0
        set Q0 0
        set Q1 1
        set Q2 2
        cphase Q1 Q2
        h Q1
        cnot Q2 Q0
        """
        ),
    ],
)
def test_mapping(text_subroutine: str):
    """
    Test whether the NV compiler correctly maps gates by comparing the matrices
    representing these gates. For this it's sufficient to have simple (incomplete, e.g. no alloc) subroutines.
    """
    vanilla_subroutine = parse_text_subroutine(text_subroutine)
    vanilla_matrix = _subroutine_as_matrix(vanilla_subroutine)
    print(f"vanilla: {vanilla_matrix}")

    compiled_subroutine = NVSubroutineCompiler(vanilla_subroutine).compile()
    compiled_matrix = _subroutine_as_matrix(compiled_subroutine)
    print(f"compiled: {np.round(compiled_matrix, 2)}")
    print(compiled_subroutine)

    assert True  # TODO: test mapping of controlled-rotation gates
    # assert are_matrices_equal(vanilla_matrix, compiled_matrix)


def test_compiling_nv():
    text_subroutine = """
# NETQASM 0.0
# APPID 0
set Q0 0
qalloc Q0
init Q0
x Q0
y Q0
z Q0
h Q0
k Q0
s Q0
t Q0
rot_x Q0 1 2
rot_y Q0 1 2
rot_z Q0 1 2
"""
    original_subroutine = parse_text_subroutine(text_subroutine)
    print(f"before compiling: {original_subroutine}")
    subroutine = NVSubroutineCompiler(original_subroutine).compile()
    print(f"after compiling: {subroutine}")

    for instr in subroutine.commands:
        assert instr.__class__ not in VanillaFlavour().instrs


@pytest.mark.parametrize(
    "subroutine_str",
    [
        (
            """
        # NETQASM 0.0
        # APPID 0
        set Q0 0
        qalloc Q0
        init Q0
        set Q1 1
        qalloc Q1
        init Q1
        cnot Q0 Q1
        """
        ),
        (
            """
        # NETQASM 0.0
        # APPID 0
        set Q0 0
        qalloc Q0
        init Q0
        set Q1 1
        qalloc Q1
        init Q1
        cphase Q1 Q0
        """
        ),
    ],
)
def test_compiling_nv_text(subroutine_str):
    original = parse_text_subroutine(subroutine_str)
    print(f"before compiling: {original}")
    compiled = NVSubroutineCompiler(original).compile()
    print(f"after compiling: {compiled}")

    for instr in compiled.commands:
        assert instr.__class__ not in VanillaFlavour().instrs


def test_compiling_nv_using_sdk():
    set_log_level("DEBUG")
    with DebugConnection("Alice", compiler=NVSubroutineCompiler) as alice:
        q = Qubit(alice)
        q.X()
        q.Y()
        q.Z()
        q.H()
        q.K()
        q.S()
        q.T()
        q.rot_X(n=1, d=2)
        q.rot_Y(n=1, d=2)
        q.rot_Z(n=1, d=2)

    assert len(alice.storage) == 4
    raw_subroutine = deserialize_message(raw=alice.storage[1]).subroutine
    subroutine = deserialize_subroutine(raw_subroutine, flavour=NVFlavour())

    # NOTE this does not test much anymore since we need to state which flavour we
    # are using to be able to deserialize
    for instr in subroutine.commands:
        assert instr.__class__ not in VanillaFlavour().instrs


if __name__ == "__main__":
    test_compiling_nv_using_sdk()
