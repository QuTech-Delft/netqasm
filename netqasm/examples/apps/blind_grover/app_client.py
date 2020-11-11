import numpy as np

from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.examples.lib.bqc import teleport_state, send_meas_cmd, recv_meas_outcome

logger = get_netqasm_logger()


def get_phi_for_oracle(b0, b1):
    """Compute the angles `phi1` and `phi2` needed to simulate
    an oracle that only tags the input (b0, b1).
    """
    phi1 = np.pi / 2 - b0 * np.pi
    phi2 = (1 - (b0 ^ b1)) * np.pi
    return phi1, phi2


def main(
        app_config=None,
        b0=0,
        b1=0,
        r1=0,
        r2=0,
        theta1=0.0,
        theta2=0.0):

    socket = Socket("client", "server", log_config=app_config.log_config)
    epr_socket = EPRSocket("server")

    client = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )

    num_qubits = 4
    phi1, phi2 = get_phi_for_oracle(b0, b1)

    # Set theta0 and theta3 to 0.
    theta = [0 for _ in range(num_qubits)]
    theta[1] = theta1
    theta[2] = theta2

    with client:
        # Teleport states q0 to q3 to the Server.
        # The resulting state q[i] might have a phase `pi`,
        # depending on outcome m[i].
        m = [None] * num_qubits
        for i in range(num_qubits):
            m[i] = teleport_state(epr_socket, theta[i])
        client.flush()

        # Convert outcomes to integers to use them in calculations below.
        m = [int(m[i]) for i in range(num_qubits)]

        # Let the Server measure q1. We want to measure with angle phi1,
        # but send delta1 instead, which compensates for m1, r1 and theta1.
        delta1 = phi1 - theta[1] + r1 * np.pi - m[1] * np.pi
        send_meas_cmd(socket, delta1)
        s1 = recv_meas_outcome(socket)

        # Let the Server measure q2. We want to measure with angle phi2,
        # but send delta2 instead, which compensates for m1, s1, r1, and theta2.
        delta2 = phi2 - theta[2] + (s1 ^ r1) * np.pi + r2 * np.pi - m[2] * np.pi
        send_meas_cmd(socket, delta2)
        s2 = recv_meas_outcome(socket)

        # At this point, and before the Server measures both output qubits (q0 and q3)
        # in the Y basis, there are still some Pauli byproducts.
        # For q0, these byproducts are Z^m0 X^s1 X^r1.
        # For q3, these byproducts are Z^m3 X^s2 X^r2.
        # However, since these all commute with Y, we will simply let
        # the Server measure Y anyway, and apply bit-flips afterwards.
        result0 = recv_meas_outcome(socket)
        result1 = recv_meas_outcome(socket)

        # Flip bits according to Pauli byproducts (^ = xor).
        if (s1 ^ r1 ^ m[0]) == 1:
            result0 = 1 - result0
        if (s2 ^ r2 ^ m[3]) == 1:
            result1 = 1 - result1

        return {
            "result0": result0,
            "result1": result1,
            "phi1": phi1,
            "phi2": phi2,
            "delta1": delta1,
            "delta2": delta2,
            "s1": s1,
            "s2": s2,
            "m": m,
            "b0": b0,
            "b1": b1,
            "r1": r1,
            "r2": r2,
            "theta1": theta[1],
            "theta2": theta[2],
        }
