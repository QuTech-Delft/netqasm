from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.logging.glob import set_log_level

DebugConnection.node_ids = {
    "Alice": 0,
    "Bob": 1,
}


def main(no_output=False):
    num = 10

    epr_socket = EPRSocket(remote_app_name="Bob")
    with DebugConnection("Alice", epr_sockets=[epr_socket]) as alice:

        outcomes = alice.new_array(num)

        with epr_socket.create_context(number=num, sequential=True) as (q, pair):
            q.H()
            outcome = outcomes.get_future_index(pair)
            q.measure(outcome)

    if no_output:
        print(f'binary:\n{alice.storage[2]}')


if __name__ == "__main__":
    set_log_level('INFO')
    main()
