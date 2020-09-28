import pytest
from collections import defaultdict

from qlink_interface import EPRType

from netqasm.sdk import EPRSocket
from netqasm.run.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging import get_netqasm_logger
from netqasm.settings import get_simulator, Simulator

logger = get_netqasm_logger()

outcomes = defaultdict(list)

num = 10


def run_alice():
    epr_socket = EPRSocket("Bob")
    with NetQASMConnection("Alice", epr_sockets=[epr_socket]):
        ent_infos = epr_socket.create(number=num, tp=EPRType.M)
        for ent_info in ent_infos:
            outcomes['Alice'].append(ent_info.measurement_outcome)


def run_bob():
    epr_socket = EPRSocket("Alice")
    with NetQASMConnection("Bob", epr_sockets=[epr_socket]):
        ent_infos = epr_socket.recv(number=num, tp=EPRType.M)
        for ent_info in ent_infos:
            outcomes['Bob'].append(ent_info.measurement_outcome)


@pytest.mark.skipif(
    get_simulator() == Simulator.SIMULAQRON,
    reason="Type M create requests are not yet supported in simulaqron",
)
def test_create_epr_m():
    run_applications([
        default_app_config("Alice", run_alice),
        default_app_config("Bob", run_bob),
    ], use_app_config=False)

    print(outcomes)
    for i in range(num):
        assert int(outcomes['Alice'][i]) == int(outcomes['Bob'][i])
