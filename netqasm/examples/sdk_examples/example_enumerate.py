import random

from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.qubit import Qubit
from netqasm.logging.glob import set_log_level


def main(no_output=False):
    with DebugConnection("Alice") as alice:
        num = 10

        outcomes = alice.new_array(num)
        rand_nums = alice.new_array(init_values=[random.randint(0, 1) for _ in range(num)])

        with rand_nums.enumerate() as (i, r):
            q = Qubit(alice)
            with r.if_eq(1):
                q.X()
            q.measure(future=outcomes.get_future_index(i))

    if no_output:
        print(f'binary:\n{alice.storage[0]}')


if __name__ == "__main__":
    set_log_level('INFO')
    main()
