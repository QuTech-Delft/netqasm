from netqasm.sdk import Qubit
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging.glob import get_netqasm_logger

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
    run_applications([
        default_app_config("Alice", run_alice),
    ], use_app_config=False)
