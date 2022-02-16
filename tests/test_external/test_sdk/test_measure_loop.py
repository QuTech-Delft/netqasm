from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.application import default_app_instance
from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, simulate_application

logger = get_netqasm_logger()


def run_alice():
    with NetQASMConnection("Alice") as alice:
        num = 100

        outcomes = alice.new_array(num)

        def body(alice, _):
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
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
        ]
    )
    simulate_application(app_instance, use_app_config=False, enable_logging=False)
