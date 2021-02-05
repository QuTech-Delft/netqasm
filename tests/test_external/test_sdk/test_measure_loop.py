from netqasm.sdk import Qubit
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging.glob import get_netqasm_logger

logger = get_netqasm_logger()


def run_alice():
    with NetQASMConnection("Alice") as alice:
        num = 100

        outcomes = alice.new_array(num)

        def body(alice):
            q = Qubit(alice)
            q.H()
            q.measure(future=outcomes.get_future_index("R0"))

        alice.loop_body(body, stop=num, loop_register="R0")
        alice.flush()
        assert len(outcomes) == num
        avg = sum(outcomes) / num
        logger.info(f"Average: {avg}")
        assert 0.4 <= avg <= 0.6


def test_measure_loop():
    run_applications([
        default_app_config("Alice", run_alice),
    ], use_app_config=False)
