import numpy as np
import pytest

from netqasm.lang.instr.core import LoadInstruction, SetInstruction
from netqasm.lang.operand import Immediate
from netqasm.lang.subroutine import Subroutine
from netqasm.logging.glob import get_netqasm_logger
from netqasm.qlink_compat import BellState
from netqasm.runtime.application import default_app_instance
from netqasm.runtime.settings import Simulator, get_simulator
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, simulate_application

logger = get_netqasm_logger()


def simulate_different_bell_state(
    subrt: Subroutine, bell_state: BellState
) -> Subroutine:
    # Change "Load bell state index from array" instruction into a simple "set"
    # It is always the second 'load' instruction in the subroutine.
    found_first_load = False
    instr_index = None
    for i, instr in enumerate(subrt.instructions):
        if isinstance(instr, LoadInstruction):
            if not found_first_load:
                found_first_load = True
            else:
                instr_index = i
                break

    assert instr_index is not None

    orig_instr: LoadInstruction = subrt.instructions[instr_index]  # type: ignore
    subrt.instructions[instr_index] = SetInstruction(
        reg=orig_instr.reg, imm=Immediate(bell_state.value)
    )
    return subrt


def post_function(backend):
    alice_state = backend.nodes["Alice"].qmemory._get_qubits(0)[0].qstate
    bob_state = backend.nodes["Bob"].qmemory._get_qubits(0)[0].qstate
    assert alice_state is bob_state
    expected_state = np.array(
        [[0.5, 0, 0, 0.5], [0, 0, 0, 0], [0, 0, 0, 0], [0.5, 0, 0, 0.5]]
    )

    logger.info(f"state = {alice_state.qrepr.reduced_dm()}")
    assert np.all(np.isclose(expected_state, alice_state.qrepr.reduced_dm()))


def run_alice():
    epr_socket = EPRSocket("Bob")
    with NetQASMConnection("Alice", epr_sockets=[epr_socket]):
        # Create entanglement
        epr_socket.create_keep()[0]


def run_bob_phi_plus():
    epr_socket = EPRSocket("Alice")
    with NetQASMConnection("Bob", epr_sockets=[epr_socket]):
        epr_socket.recv_keep()


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="SimulaQron does not yet support a post_function",
)
def test_create_epr_phi_plus():
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
            ("Bob", run_bob_phi_plus),
        ]
    )
    simulate_application(
        app_instance,
        use_app_config=False,
        post_function=post_function,
        enable_logging=False,
    )


def run_bob_phi_minus():
    epr_socket = EPRSocket("Alice")
    with NetQASMConnection("Bob", epr_sockets=[epr_socket]) as conn:
        [q] = epr_socket.recv_keep()
        subrt = conn.compile()
        # pretend PHI_MINUS was generated
        subrt2 = simulate_different_bell_state(subrt, BellState.PHI_MINUS)
        conn.commit_subroutine(subrt2)
        # compiler should apply a Z, undo it:
        q.Z()


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="SimulaQron does not yet support a post_function",
)
def test_create_epr_phi_minus():
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
            ("Bob", run_bob_phi_minus),
        ]
    )
    simulate_application(
        app_instance,
        use_app_config=False,
        post_function=post_function,
        enable_logging=False,
    )


def run_bob_psi_plus():
    epr_socket = EPRSocket("Alice")
    with NetQASMConnection("Bob", epr_sockets=[epr_socket]) as conn:
        [q] = epr_socket.recv_keep()
        subrt = conn.compile()
        # pretend PSI_PLUS was generated
        subrt2 = simulate_different_bell_state(subrt, BellState.PSI_PLUS)
        conn.commit_subroutine(subrt2)
        # compiler should apply an X, undo it:
        q.X()


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="SimulaQron does not yet support a post_function",
)
def test_create_epr_psi_plus():
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
            ("Bob", run_bob_psi_plus),
        ]
    )
    simulate_application(
        app_instance,
        use_app_config=False,
        post_function=post_function,
        enable_logging=False,
    )


def run_bob_psi_minus():
    epr_socket = EPRSocket("Alice")
    with NetQASMConnection("Bob", epr_sockets=[epr_socket]) as conn:
        [q] = epr_socket.recv_keep()
        subrt = conn.compile()
        # pretend PSI_MINUS was generated
        subrt2 = simulate_different_bell_state(subrt, BellState.PSI_MINUS)
        conn.commit_subroutine(subrt2)
        # compiler should apply an X and a Z, undo it:
        q.Z()
        q.X()


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="SimulaQron does not yet support a post_function",
)
def test_create_epr_psi_minus():
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
            ("Bob", run_bob_psi_minus),
        ]
    )
    simulate_application(
        app_instance,
        use_app_config=False,
        post_function=post_function,
        enable_logging=False,
    )


if __name__ == "__main__":
    test_create_epr_phi_plus()
    test_create_epr_phi_minus()
    test_create_epr_psi_plus()
    test_create_epr_psi_minus()
