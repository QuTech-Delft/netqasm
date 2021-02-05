from netqasm.sdk import Qubit
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging.glob import get_netqasm_logger

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
        assert 0.4 <= avg <= 0.6


def test_measure():
    run_applications([
        default_app_config("Alice", run_alice),
    ], use_app_config=False)
