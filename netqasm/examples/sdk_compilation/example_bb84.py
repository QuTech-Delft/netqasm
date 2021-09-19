import random

from netqasm.logging.glob import set_log_level
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.epr_socket import EPRSocket

DebugConnection.node_ids = {
    "Alice": 0,
    "Bob": 1,
}


def main(no_output=False):
    n = 10

    epr_socket = EPRSocket(remote_app_name="Bob")
    with DebugConnection("Alice", epr_sockets=[epr_socket]) as alice:
        bit_flips = alice.new_array(
            init_values=[random.randint(0, 1) for _ in range(n)]
        )
        basis_flips = alice.new_array(
            init_values=[random.randint(0, 1) for _ in range(n)]
        )
        outcomes = alice.new_array(n)

        with epr_socket.create_context(number=n, sequential=True) as (q, pair):
            with bit_flips.get_future_index(pair).if_eq(1):
                q.X()
            with basis_flips.get_future_index(pair).if_eq(1):
                q.H()
            outcome = outcomes.get_future_index(pair)
            q.measure(outcome)

    if no_output:
        # Third message since the first two are for init application
        # and opening the EPR socket
        print(f"binary:\n{alice.storage[2]}")


if __name__ == "__main__":
    set_log_level("INFO")
    main()
