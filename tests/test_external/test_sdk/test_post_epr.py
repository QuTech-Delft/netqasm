from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.application import default_app_instance
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, simulate_application

logger = get_netqasm_logger()

num = 10


def run_alice():
    epr_socket = EPRSocket("bob")
    with NetQASMConnection("alice", epr_sockets=[epr_socket]) as alice:

        outcomes = alice.new_array(num)

        def post_create(conn, q, pair):
            q.H()
            outcome = outcomes.get_future_index(pair)
            q.measure(outcome)

        epr_socket.create(number=num, post_routine=post_create, sequential=True)

    return list(outcomes)


def run_bob():
    epr_socket = EPRSocket("alice")
    with NetQASMConnection("bob", epr_sockets=[epr_socket]) as bob:

        outcomes = bob.new_array(num)

        def post_recv(conn, q, pair):
            q.H()
            outcome = outcomes.get_future_index(pair)
            q.measure(outcome)

        epr_socket.recv(number=num, post_routine=post_recv, sequential=True)

    return list(outcomes)


def test_post_epr():
    app_instance = default_app_instance(
        [
            ("alice", run_alice),
            ("bob", run_bob),
        ]
    )
    results = simulate_application(
        app_instance, use_app_config=False, enable_logging=False
    )[0]
    print(results)

    assert results["app_alice"] == results["app_bob"]


if __name__ == "__main__":
    for _ in range(100):
        test_post_epr()
