import random

from netqasm.sdk.connection import DebugConnection
from netqasm.logging import set_log_level

DebugConnection.set_node_ids({
    "Alice": 0,
    "Bob": 1,
})


def main():
    n = 10

    with DebugConnection("Alice", epr_to="Bob", track_lines=True) as alice:
        bit_flips = alice.new_array(init_values=[random.randint(0, 1) for _ in range(n)])
        basis_flips = alice.new_array(init_values=[random.randint(0, 1) for _ in range(n)])
        outcomes = alice.new_array(n)

        with alice.create_epr_context("Bob", number=n, sequential=True) as (q, pair):
            with bit_flips.get_future_index(pair).if_eq(1):
                q.X()
            with basis_flips.get_future_index(pair).if_eq(1):
                q.H()
            outcome = outcomes.get_future_index(pair)
            q.measure(outcome)

    print(f'binary:\n{alice.storage[0]}')


if __name__ == "__main__":
    set_log_level('INFO')
    main()
