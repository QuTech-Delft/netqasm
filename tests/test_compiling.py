import pytest
from netqasm.logging import set_log_level
from netqasm.parsing import parse_text_subroutine, deserialize
# from netqasm.quantum_gates import gate_to_matrix, are_matrices_equal
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.qubit import Qubit
from netqasm.compiling import NVSubroutineCompiler

from netqasm.instructions.flavour import VanillaFlavour, NVFlavour


# @pytest.mark.parametrize(
#     'abstract_gate, nv_gates',
#     NVSubroutineCompiler.SINGLE_QUBIT_GATE_MAPPING.items(),
# )
# def test_mapping(abstract_gate, nv_gates):
#     abstract_matrix = gate_to_matrix(abstract_gate)
#     nv_matrix = gate_to_matrix(*nv_gates[0])
#     for nv_gate in nv_gates[1:]:
#         nv_matrix = nv_matrix @ gate_to_matrix(*nv_gate)
#     print(f'abstract_matrix = {abstract_matrix}')
#     print(f'nv_matrix = {nv_matrix}')
#     assert are_matrices_equal(abstract_matrix, nv_matrix)


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
        assert (
            instr.__class__ not in VanillaFlavour().instrs
        )


@pytest.mark.parametrize("subroutine_str", [
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
    )
])
def test_compiling_nv_text(subroutine_str):
    original = parse_text_subroutine(subroutine_str)
    print(f"before compiling: {original}")
    compiled = NVSubroutineCompiler(original).compile()
    print(f"after compiling: {compiled}")

    for instr in compiled.commands:
        assert (
            instr.__class__ not in VanillaFlavour().instrs
        )


def test_compiling_nv_using_sdk():
    set_log_level('DEBUG')
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
    subroutine = deserialize(alice.storage[1].msg, flavour=NVFlavour())

    for instr in subroutine.commands:
        assert (
            instr.__class__ not in VanillaFlavour().instrs
        )


if __name__ == '__main__':
    test_compiling_nv_using_sdk()
