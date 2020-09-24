import random
import numpy as np
import netsquid as ns

from netqasm.logging import get_netqasm_logger
from netqasm.run.app_config import AppConfig
from netqasm.sdk.external import run_applications

from examples.apps.blind_rotation.app_alice import main as blind_rotation_alice
from examples.apps.blind_rotation.app_bob import main as blind_rotation_bob

from examples.apps.blind_grover.app_alice import main as blind_grover_alice
from examples.apps.blind_grover.app_bob import main as blind_grover_bob

logger = get_netqasm_logger()


def fidelity_ok(qstate1, dm2, threshold=0.999):
    fidelity = qstate1.fidelity(dm2)
    return fidelity > threshold


def run_blind_rotation():
    num_iter = 4
    num_qubits = num_iter + 1
    phi = [random.uniform(0, 2 * np.pi) for _ in range(num_iter)]
    theta = [random.uniform(0, 2 * np.pi) for _ in range(num_qubits)]
    r = [random.randint(0, 1) for _ in range(num_iter)]

    alice_app_inputs = {
        'num_iter': num_iter,
        'theta': theta,
        'phi': phi,
        'r': r
    }

    bob_app_inputs = {
        'num_iter': num_iter
    }

    applications = [
        AppConfig(
            app_name="alice",
            node_name="alice",
            main_func=blind_rotation_alice,
            log_config=None,
            inputs=alice_app_inputs
        ),
        AppConfig(
            app_name="bob",
            node_name="bob",
            main_func=blind_rotation_bob,
            log_config=None,
            inputs=bob_app_inputs
        ),
    ]

    results = run_applications(applications)

    output_state = results['app_bob']['output_state']
    s = results['app_alice']['s']
    m = results['app_alice']['m']
    r = results['app_alice']['r']
    theta = results['app_alice']['theta']

    s.extend([0, 0])
    m.extend([0, 0])
    r.extend([0, 0])

    # output should be (n = num_iter):
    # Rz(theta[n]) Z^m[n] X^{s[n-1]^r[n-1]} Z^{s[n-2]^r[n-2]} H Rz(phi[n-1]) H Rz(phi[n-2] ... |+>
    ref = ns.qubits.create_qubits(1)[0]
    ns.qubits.operate(ref, ns.H)
    for i in range(num_iter):
        ns.qubits.operate(ref, ns.qubits.create_rotation_op(phi[i], (0, 0, 1)))
        ns.qubits.operate(ref, ns.H)
    if m[num_iter] == 1:
        ns.qubits.operate(ref, ns.Z)
    if (s[num_iter - 1] ^ r[num_iter - 1]) == 1:
        ns.qubits.operate(ref, ns.X)
    if (s[num_iter - 2] ^ r[num_iter - 2]) == 1:
        ns.qubits.operate(ref, ns.Z)
    ns.qubits.operate(ref, ns.qubits.create_rotation_op(theta[num_iter], (0, 0, 1)))

    assert fidelity_ok(ref.qstate, np.array(output_state))


def test_blind_rotation():
    num = 3
    for _ in range(num):
        run_blind_rotation()


def run_blind_grover():
    b0 = random.randint(0, 1)
    b1 = random.randint(0, 1)

    r1 = random.randint(0, 1)
    r2 = random.randint(0, 1)

    theta1 = random.uniform(0, 2 * np.pi)
    theta2 = random.uniform(0, 2 * np.pi)

    alice_app_inputs = {
        'b0': b0,
        'b1': b1,
        'r1': r1,
        'r2': r2,
        'theta1': theta1,
        'theta2': theta2
    }

    bob_app_inputs = {}

    applications = [
        AppConfig(
            app_name="alice",
            node_name="alice",
            main_func=blind_grover_alice,
            log_config=None,
            inputs=alice_app_inputs
        ),
        AppConfig(
            app_name="bob",
            node_name="bob",
            main_func=blind_grover_bob,
            log_config=None,
            inputs=bob_app_inputs
        ),
    ]

    results = run_applications(applications)

    m0 = results['app_alice']['result0']
    m1 = results['app_alice']['result1']

    assert b0 == m0
    assert b1 == m1


def test_blind_grover():
    num = 3
    for _ in range(num):
        run_blind_grover()


if __name__ == '__main__':
    run_blind_rotation()
    run_blind_grover()
