import numpy as np
import pytest

from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.application import default_app_instance
from netqasm.runtime.settings import Simulator, get_simulator
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, simulate_application

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
        [[0.5, 0, 0, 0.5], [0, 0, 0, 0], [0, 0, 0, 0], [0.5, 0, 0, 0.5]]
    )

    logger.info(f"state = {alice_state.qrepr.reduced_dm()}")
    assert np.all(np.isclose(expected_state, alice_state.qrepr.reduced_dm()))


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="SimulaQron does not yet support a post_function",
)
def test_create_epr():
    # app_instance = default_app_instance([
    #     ("Alice", run_alice),
    #     ("Bob", run_bob),
    # ])
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
            ("Bob", run_bob),
        ]
    )
    simulate_application(
        app_instance,
        use_app_config=False,
        post_function=post_function,
        enable_logging=False,
    )


if __name__ == "__main__":
    test_create_epr()
