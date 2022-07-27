from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.application import default_app_instance
from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, simulate_application
from netqasm.sdk.qubit import QubitMeasureBasis

logger = get_netqasm_logger()


def run_alice():
    with NetQASMConnection("Alice") as alice:
        outcomes = []
        num = 10
        for _ in range(num):
            q = Qubit(alice)
            q.H()
            q.Z()
            # q should be in |->
            m = q.measure(basis=QubitMeasureBasis.X)
            alice.flush()
            outcomes.append(m)
        assert all(m == 1 for m in outcomes)


def test_measure():
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
        ]
    )
    simulate_application(app_instance, use_app_config=False, enable_logging=False)


if __name__ == "__main__":
    # set_log_level("DEBUG")
    test_measure()
