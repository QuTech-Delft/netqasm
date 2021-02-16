import math

from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.examples.lib.bqc import teleport_state, send_meas_cmd, recv_meas_outcome

logger = get_netqasm_logger()


def main(app_config=None, num_iter=2, alpha=0, beta=0, theta1=0, theta2=0, r1=0, r2=0):
    socket = Socket("client", "server", log_config=app_config.log_config)
    epr_socket = EPRSocket("server")

    client = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )

    with client:
        # Remote state prepration of 2 qubits.
        # The resulting states might have a phase `pi`,
        # depending on outcome p.
        p1 = teleport_state(epr_socket, theta1)
        p2 = teleport_state(epr_socket, theta2)
        client.flush()

        # Convert outcomes to integers to use them in calculations below.
        p1, p2 = int(p1), int(p2)

        # Send first angle to server.
        delta1 = alpha - theta1 + (p1 + r1) * math.pi
        send_meas_cmd(socket, delta1)
        m1 = recv_meas_outcome(socket)

        # Send second angle to server.
        delta2 = math.pow(-1, (m1 + r1)) * beta - theta2 + (p2 + r2) * math.pi
        send_meas_cmd(socket, delta2)
        m2 = recv_meas_outcome(socket)

        return {
            "delta1": delta1,
            "delta2": delta2,
            "p1": p1,
            "p2": p2,
            "m1": m1,
            "m2": m2,
        }
