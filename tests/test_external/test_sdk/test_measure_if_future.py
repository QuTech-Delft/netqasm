from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.application import default_app_instance
from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, simulate_application

logger = get_netqasm_logger()


def run_alice():
    num = 10
    with NetQASMConnection("Alice") as alice:
        for _ in range(num):
            q = Qubit(alice)
            q.H()
            m = q.measure(inplace=True)
            with m.if_eq(1):
                q.X()

            zero = q.measure()
            alice.flush()
            assert zero == 0


def test_measure_if_future():
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
        ]
    )
    simulate_application(app_instance, use_app_config=False, enable_logging=False)
