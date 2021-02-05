from netqasm.sdk import Qubit
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging.glob import get_netqasm_logger

logger = get_netqasm_logger()


def run_alice():
    with NetQASMConnection("Alice") as alice:
        half = 5
        num = half * 2

        outcomes = alice.new_array(num)
        even = alice.new_array(init_values=[0]).get_future_index(0)

        with alice.loop(num) as i:
            q = Qubit(alice)
            with even.if_eq(0):
                q.X()
            outcome = outcomes.get_future_index(i)
            q.measure(outcome)
            even.add(1, mod=2)

        alice.flush()
        assert len(outcomes) == num
        print(f'outcomes = {list(outcomes)}')
        expected = [1, 0] * half
        print(f'expected = {expected}')
        assert list(outcomes) == expected


def test_measure_loop_context():
    run_applications([
        default_app_config("Alice", run_alice),
    ], use_app_config=False)
