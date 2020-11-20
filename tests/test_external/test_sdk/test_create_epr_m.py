from qlink_interface import EPRType

from netqasm.sdk import EPRSocket
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging.glob import get_netqasm_logger

logger = get_netqasm_logger()

num = 10


def run_alice():
    epr_socket = EPRSocket("bob")
    outcomes = []
    with NetQASMConnection("alice", epr_sockets=[epr_socket]):
        ent_infos = epr_socket.create(number=num, tp=EPRType.M)
        for ent_info in ent_infos:
            outcomes.append(ent_info.measurement_outcome)
    return outcomes


def run_bob():
    epr_socket = EPRSocket("alice")
    outcomes = []
    with NetQASMConnection("bob", epr_sockets=[epr_socket]):
        ent_infos = epr_socket.recv(number=num, tp=EPRType.M)
        for ent_info in ent_infos:
            outcomes.append(ent_info.measurement_outcome)
    return outcomes


def test_create_epr_m():
    outcomes = run_applications([
        default_app_config("alice", run_alice),
        default_app_config("bob", run_bob),
    ], use_app_config=False)

    print(outcomes)
    for i in range(num):
        assert int(outcomes['app_alice'][i]) == int(outcomes['app_bob'][i])
