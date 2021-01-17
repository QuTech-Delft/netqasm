import pytest
import numpy as np

from netqasm.sdk import EPRSocket
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, simulate_application
from netqasm.sdk.external import NetQASMConnection
from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.settings import get_simulator, Simulator

from netqasm.runtime.application import Application, ApplicationInstance, Program, default_app_instance

logger = get_netqasm_logger()


def run_alice():
    epr_socket = EPRSocket("Bob")
    with NetQASMConnection("Alice", epr_sockets=[epr_socket]):
        # Create entanglement
        epr_socket.create()[0]


def run_bob():
    epr_socket = EPRSocket("Alice")
    with NetQASMConnection("Bob", epr_sockets=[epr_socket]):
        epr_socket.recv()


def post_function(backend):
    alice_state = backend.nodes["Alice"].qmemory._get_qubits(0)[0].qstate
    bob_state = backend.nodes["Bob"].qmemory._get_qubits(0)[0].qstate
    assert alice_state is bob_state
    expected_state = np.array(
        [[0.5, 0, 0, 0.5],
         [0, 0, 0, 0],
         [0, 0, 0, 0],
         [0.5, 0, 0, 0.5]])

    logger.info(f"state = {alice_state.dm}")
    assert np.all(np.isclose(expected_state, alice_state.dm))


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="SimulaQron does not yet support a post_function",
)
def test_create_epr():
    # run_applications([
    #     default_app_config("Alice", run_alice),
    #     default_app_config("Bob", run_bob),
    # ], use_app_config=False, post_function=post_function)
    app_instance = default_app_instance([
        ("Alice", run_alice),
        ("Bob", run_bob),
    ])
    simulate_application(app_instance, use_app_config=False, post_function=post_function)


if __name__ == "__main__":
    test_create_epr()
