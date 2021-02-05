import random

from netqasm.sdk import Qubit
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging.glob import get_netqasm_logger

logger = get_netqasm_logger()


def run_alice():
    with NetQASMConnection("Alice") as alice:
        num = 10

        outcomes = alice.new_array(num)
        rand_nums = alice.new_array(num, init_values=[random.randint(0, 1) for _ in range(num)])
        i = alice.new_array(1, init_values=[0]).get_future_index(0)

        with rand_nums.foreach() as r:
            q = Qubit(alice)
            with r.if_eq(1):
                q.X()
            q.measure(future=outcomes.get_future_index(i))
            i.add(1)

        alice.flush()
        assert len(outcomes) == num
        print(f'rand_nums = {list(rand_nums)}')
        print(f'outcomes = {list(outcomes)}')
        assert list(rand_nums) == list(outcomes)


def test_foreach():
    run_applications([
        default_app_config("Alice", run_alice),
    ], use_app_config=False)
