from netqasm.logging.glob import get_netqasm_logger
from netqasm.qlink_compat import BellState
from netqasm.runtime.application import default_app_instance
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, simulate_application

logger = get_netqasm_logger()

num = 10


def run_alice():
    epr_socket = EPRSocket("bob")
    outcomes = []
    with NetQASMConnection("alice", epr_sockets=[epr_socket]):
        ent_infos = epr_socket.create_measure(number=num)
        for ent_info in ent_infos:
            outcomes.append(ent_info.raw_measurement_outcome)
    return outcomes


def run_bob():
    epr_socket = EPRSocket("alice")
    outcomes = []
    with NetQASMConnection("bob", epr_sockets=[epr_socket]):
        ent_infos = epr_socket.recv_measure(number=num)
        for ent_info in ent_infos:
            outcomes.append(ent_info.raw_measurement_outcome)
    return outcomes


def test_create_epr_m():
    app_instance = default_app_instance(
        [
            ("alice", run_alice),
            ("bob", run_bob),
        ]
    )
    outcomes = simulate_application(
        app_instance, use_app_config=False, enable_logging=False
    )[0]

    alice_outcomes = [int(m) for m in outcomes["app_alice"]]
    bob_outcomes = [int(m) for m in outcomes["app_bob"]]
    print(alice_outcomes)
    print(bob_outcomes)
    assert all(i == j for i, j in zip(alice_outcomes, bob_outcomes))


def run_alice_psi_plus():
    epr_socket = EPRSocket("bob")
    outcomes = []

    with NetQASMConnection("alice", epr_sockets=[epr_socket]):
        results = epr_socket.create_measure(number=num)

    for result in results:
        # Pretend we had Psi+ instead of Phi+.
        # Post-processing should make up for this.
        result.raw_bell_state._value = BellState.PSI_PLUS.value
        result.post_process = True
        outcomes.append(result.measurement_outcome)
    return outcomes


def run_bob_psi_plus():
    epr_socket = EPRSocket("alice")
    outcomes = []

    with NetQASMConnection("bob", epr_sockets=[epr_socket]):
        results = epr_socket.recv_measure(number=num)

    for result in results:
        # Pretend we had Psi+ instead of Phi+ by flipping the bit
        outcomes.append(int(result.raw_measurement_outcome) ^ 1)
    return outcomes


def test_create_epr_m_psi_plus():
    app_instance = default_app_instance(
        [
            ("alice", run_alice_psi_plus),
            ("bob", run_bob_psi_plus),
        ]
    )
    outcomes = simulate_application(
        app_instance, use_app_config=False, enable_logging=False
    )[0]

    alice_outcomes = [int(m) for m in outcomes["app_alice"]]
    bob_outcomes = [int(m) for m in outcomes["app_bob"]]
    print(alice_outcomes)
    print(bob_outcomes)
    assert all(i == j for i, j in zip(alice_outcomes, bob_outcomes))


if __name__ == "__main__":
    test_create_epr_m()
    test_create_epr_m_psi_plus()
