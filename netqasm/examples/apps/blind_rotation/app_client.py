import random
import numpy as np

from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.examples.lib.bqc import teleport_state, send_meas_cmd, recv_meas_outcome

logger = get_netqasm_logger()


def main(app_config=None, num_iter=3, theta=None, phi=None, r=None):
    socket = Socket("client", "server", log_config=app_config.log_config)
    epr_socket = EPRSocket("server")

    client = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )

    num_qubits = num_iter + 1

    if theta is None:
        theta = [0 for _ in range(num_qubits)]
    if phi is None:
        phi = [random.uniform(0, 2 * np.pi) for _ in range(num_iter)]
    if r is None:
        r = [0 for _ in range(num_iter)]

    with client:
        # Teleport states q[0] to q[num_qubits - 1] to the Server.
        # The resulting state q[i] might have a phase `pi`,
        # depending on outcome m[i].
        m = [None] * num_qubits
        for i in range(num_qubits):
            m[i] = teleport_state(epr_socket, theta[i])
        client.flush()

        # Convert outcomes to integers to use them in calculations below.
        m = [int(m[i]) for i in range(num_qubits)]

        # delta[i] will hold the actual measurement angle sent to the Server.
        delta = [None] * num_iter
        # s[i] will hold the measurement outcome for qubit q[i].
        s = [None] * num_iter

        # For r and s, temporarily add two 0s at the end,
        # so that we can use indices -1 and -2 for convenience.
        s.extend([0, 0])
        r.extend([0, 0])

        # Main loop. For each iteration i, we let the Server measure q[i].
        # We want to measure with angle phi[i], but initial phases
        # (m[i] and theta[i]), as well as previous measurement outcomes s[j]
        # and secret key bits r[j] are required to be compensated for.
        # The actual angle we send to the Server is then called delta[i].
        for i in range(num_iter):
            delta[i] = pow(-1, s[i-1] ^ r[i-1]) * phi[i]
            delta[i] += (s[i-2] ^ r[i-2]) * np.pi
            delta[i] += r[i] * np.pi
            # we have q[i] = Rz(m[i]*pi + theta[i]), compensate for this:
            delta[i] -= theta[i]
            delta[i] -= m[i] * np.pi

            send_meas_cmd(socket, delta[i])
            s[i] = recv_meas_outcome(socket)

        # remove last 2 temporary 0s
        s = s[0:num_iter]
        r = r[0:num_iter]

        return {
            "delta": delta,
            "s": s,
            "m": m,
            "theta": theta,
            "phi": phi,
            "r": r,
        }
