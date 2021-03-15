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

        with epr_socket.create_context(number=num, sequential=True) as (q, pair):
            q.H()
            outcome = outcomes.get_future_index(pair)
            q.measure(outcome)

    return list(outcomes)


def run_bob():
    epr_socket = EPRSocket("alice")
    with NetQASMConnection("bob", epr_sockets=[epr_socket]) as bob:

        outcomes = bob.new_array(num)

        with epr_socket.recv_context(number=num, sequential=True) as (q, pair):
            q.H()
            outcome = outcomes.get_future_index(pair)
            q.measure(outcome)

    return list(outcomes)


def test_post_epr_context():
    app_instance = default_app_instance(
        [
            ("alice", run_alice),
            ("bob", run_bob),
        ]
    )
    node_outcomes = simulate_application(
        app_instance, use_app_config=False, enable_logging=False
    )[0]

    logger.info(node_outcomes)
    assert node_outcomes["app_alice"] == node_outcomes["app_bob"]
