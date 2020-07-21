import pytest
from netqasm.logging import set_log_level
from netqasm.parsing import parse_text_subroutine, parse_binary_subroutine
from netqasm.quantum_gates import gate_to_matrix, are_matrices_equal
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.qubit import Qubit
from netqasm.instructions import Instruction, QUBIT_GATES
from netqasm.compiling import NVSubroutineCompiler

from netqasm.instr2 import core, vanilla, nv


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


def test_compiling_nv():
    text_subroutine = """
# NETQASM 0.0
# APPID 0
set Q0 0
qalloc Q0
init Q0
// x Q0
// y Q0
// z Q0
// h Q0
// k Q0
// s Q0
// t Q0
rot_x Q0 1 2
// rot_y Q0 1 2
// rot_z Q0 1 2
"""
    original_subroutine = parse_text_subroutine(text_subroutine)
    print(f"before compiling: {original_subroutine}")
    subroutine = NVSubroutineCompiler(original_subroutine).compile()
    print(f"after compiling: {subroutine}")
    # Check that all gates are now x and y rotations
    for instr in subroutine.commands:
        # instr = command.instruction
        # if instr in QUBIT_GATES:
        if (isinstance(instr, core.SingleQubitInstruction)):
            # and not (isinstance(instr, core.QAllocInstruction)
            #     or isinstance(instr, core.QFreeInstruction)
            #     or isinstance(instr, core.InitInstruction))):
            # print(f"insrt: {type(instr)}")
            # assert instr in [Instruction.ROT_X, Instruction.ROT_Y]
            assert (isinstance(instr, vanilla.RotXInstruction)
                or isinstance(instr, vanilla.RotYInstruction))


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
    subroutine = parse_binary_subroutine(alice.storage[1].msg)
    for command in subroutine.commands:
        instr = command.instruction
        if instr in QUBIT_GATES:
            assert instr in [Instruction.ROT_X, Instruction.ROT_Y]

if __name__ == '__main__':
    test_compiling_nv()