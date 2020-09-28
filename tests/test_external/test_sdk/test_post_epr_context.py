import pytest

from netqasm.sdk import EPRSocket
from netqasm.run.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging import get_netqasm_logger
from netqasm.settings import get_simulator, Simulator

logger = get_netqasm_logger()
num = 10

node_outcomes = {}


def run_alice():
    epr_socket = EPRSocket("Bob")
    with NetQASMConnection("Alice", epr_sockets=[epr_socket]) as alice:

        outcomes = alice.new_array(num)

        with epr_socket.create_context(number=num, sequential=True) as (q, pair):
            q.H()
            outcome = outcomes.get_future_index(pair)
            q.measure(outcome)

    node_outcomes["Alice"] = list(outcomes)


def run_bob():
    epr_socket = EPRSocket("Alice")
    with NetQASMConnection("Bob", epr_sockets=[epr_socket]) as bob:

        outcomes = bob.new_array(num)

        with epr_socket.recv_context(number=num, sequential=True) as (q, pair):
            q.H()
            outcome = outcomes.get_future_index(pair)
            q.measure(outcome)

    node_outcomes["Bob"] = list(outcomes)


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="Create requests with multiple pairs are not yet supported in simulaqron",
)
def test_post_epr_context():
    run_applications([
        default_app_config("Alice", run_alice),
        default_app_config("Bob", run_bob),
    ], use_app_config=False)

    logger.info(node_outcomes)
    assert node_outcomes["Alice"] == node_outcomes["Bob"]
