from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.application import default_app_instance
from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, simulate_application

logger = get_netqasm_logger()


def run_alice():
    with NetQASMConnection("Alice") as alice:
        count = 0
        num = 100
        for _ in range(num):
            q = Qubit(alice)
            q.H()
            m = q.measure()
            alice.flush()
            count += m
        avg = count / num
        logger.info(avg)
        assert 0.35 <= avg <= 0.65


def test_measure():
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
        ]
    )
    simulate_application(app_instance, use_app_config=False, enable_logging=False)
