from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.application import default_app_instance
from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, simulate_application

logger = get_netqasm_logger()


def run_alice():
    logger.debug("Starting Alice thread")
    with NetQASMConnection("Alice") as alice:
        q1 = Qubit(alice)
        q2 = Qubit(alice)
        q1.H()
        q2.X()
        q1.X()
        q2.H()
    assert len(alice.active_qubits) == 0
    logger.debug("End Alice thread")


def run_bob():
    logger.debug("Starting Bob thread")
    with NetQASMConnection("Bob") as bob:
        q1 = Qubit(bob)
        q2 = Qubit(bob)
        q1.H()
        q2.X()
        q1.X()
        q2.H()
    assert len(bob.active_qubits) == 0
    logger.debug("End Bob thread")


def test_two_nodes():
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
            ("Bob", run_bob),
        ]
    )
    simulate_application(app_instance, use_app_config=False, enable_logging=False)
