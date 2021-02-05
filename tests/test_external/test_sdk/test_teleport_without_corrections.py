import pytest
import numpy as np

from netqasm.sdk import Qubit, EPRSocket
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.settings import get_simulator, Simulator

logger = get_netqasm_logger()

# TODO depending on how post functions are implemented in simulaqron
# this should not be a variable outside `run_alice` since it won't be
# affected when running that function in a seperate process.
# We should instead use the results returned from `run_applications`.
outcomes = []


def run_alice():
    epr_socket = EPRSocket("Bob")
    with NetQASMConnection("Alice", epr_sockets=[epr_socket]) as alice:
        # Create a qubit
        q = Qubit(alice)
        q.H()

        # Create entanglement
        epr = epr_socket.create()[0]

        # Teleport
        q.cnot(epr)
        q.H()
        m1 = q.measure()
        m2 = epr.measure()
        outcomes.append(m1)
        outcomes.append(m2)


def run_bob():
    epr_socket = EPRSocket("Alice")
    with NetQASMConnection("Bob", epr_sockets=[epr_socket]):
        epr_socket.recv()


def post_function(backend):
    m1, m2 = outcomes
    logger.info(f"m1, m2 = {m1}, {m2}")
    expected_states = {
        (0, 0): np.array([[0.5, 0.5], [0.5, 0.5]]),
        (0, 1): np.array([[0.5, 0.5], [0.5, 0.5]]),
        (1, 0): np.array([[0.5, -0.5], [-0.5, 0.5]]),
        (1, 1): np.array([[0.5, -0.5], [-0.5, 0.5]]),
    }
    state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate.dm
    logger.info(f"state = {state}")
    expected = expected_states[m1, m2]
    logger.info(f"expected = {expected}")
    assert np.all(np.isclose(expected, state))


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="SimulaQron does not yet support a post_function",
)
def test_teleport_without_corrections():
    run_applications([
        default_app_config("Alice", run_alice),
        default_app_config("Bob", run_bob),
    ], use_app_config=False, post_function=post_function)
