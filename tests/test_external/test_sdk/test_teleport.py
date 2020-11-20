import pytest
import numpy as np

from netqasm.sdk import Qubit, EPRSocket
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, Socket, run_applications
from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.settings import get_simulator, Simulator

logger = get_netqasm_logger()


def run_alice():
    socket = Socket("Alice", "Bob")
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

    logger.info(f"m1, m2 = {m1}, {m2}")

    # Send the correction information
    msg = str((int(m1), int(m2)))
    socket.send(msg)


def run_bob():
    socket = Socket("Bob", "Alice")
    epr_socket = EPRSocket("Alice")
    with NetQASMConnection("Bob", epr_sockets=[epr_socket]) as bob:
        epr = epr_socket.recv()[0]
        bob.flush()

        # Get the corrections
        msg = socket.recv()
        logger.info(f"Bob got corrections: {msg}")
        m1, m2 = eval(msg)
        if m2 == 1:
            epr.X()
        if m1 == 1:
            epr.Z()


def post_function(backend):
    state = backend._nodes["Bob"].qmemory._get_qubits(0)[0].qstate.dm
    logger.info(f"state = {state}")
    expected = np.array([[0.5, 0.5], [0.5, 0.5]])
    logger.info(f"expected = {expected}")
    assert np.all(np.isclose(expected, state))


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="SimulaQron does not yet support a post_function",
)
def test_teleport():
    run_applications([
        default_app_config("Alice", run_alice),
        default_app_config("Bob", run_bob),
    ], use_app_config=False, post_function=post_function)
