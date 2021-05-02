import numpy as np
import pytest

from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.application import default_app_instance
from netqasm.runtime.settings import Simulator, get_simulator
from netqasm.sdk import EPRSocket, Qubit
from netqasm.sdk.external import NetQASMConnection, Socket, simulate_application

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
    state = backend.nodes["Bob"].qmemory._get_qubits(0)[0].qstate.qrepr.reduced_dm()
    logger.info(f"state = {state}")
    expected = np.array([[0.5, 0.5], [0.5, 0.5]])
    logger.info(f"expected = {expected}")
    assert np.all(np.isclose(expected, state))


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="SimulaQron does not yet support a post_function",
)
def test_teleport():
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
