from netqasm.sdk.connection import DebugConnection
from netqasm.logging import set_log_level

DebugConnection.set_node_ids({
    "Alice": 0,
    "Bob": 1,
})


def main():
    num = 10

    with DebugConnection("Alice", epr_to="Bob", track_lines=True) as alice:

        outcomes = alice.new_array(num)

        with alice.create_epr_context("Bob", number=num, sequential=True) as (q, pair):
            q.H()
            outcome = outcomes.get_future_index(pair)
            q.measure(outcome)

    print(f'binary:\n{alice.storage[0]}')


if __name__ == "__main__":
    set_log_level('INFO')
    main()
