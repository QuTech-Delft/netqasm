import math

from netqasm.examples.lib.bqc import recv_meas_outcome, send_meas_cmd, teleport_state
from netqasm.logging.glob import get_netqasm_logger
from netqasm.logging.output import get_new_app_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket

logger = get_netqasm_logger()


def main(app_config=None, num_iter=2, alpha=0, beta=0, theta1=0, theta2=0, r1=0, r2=0):
    socket = Socket("client", "server", log_config=app_config.log_config)
    epr_socket = EPRSocket("server")

    # Inputs are coefficients of pi, e.g. alpha=0.5 -> angle 0.5*pi
    alpha *= math.pi
    beta *= math.pi
    theta1 *= math.pi
    theta2 *= math.pi

    app_logger = get_new_app_logger(
        app_name=app_config.app_name, log_config=app_config.log_config
    )

    client = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )

    with client:
        # Remote state prepration of 2 qubits.
        # The resulting states might have a phase `pi`,
        # depending on outcome p.
        app_logger.log("Remotely preparing server's first state...")
        p1 = teleport_state(epr_socket, theta1)
        client.flush()
        app_logger.log("Remotely preparing server's second state...")
        p2 = teleport_state(epr_socket, theta2)
        client.flush()
        app_logger.log("Remote state preparation finished.")
        socket.send_silent("")

        # Convert outcomes to integers to use them in calculations below.
        p1, p2 = int(p1), int(p2)

        # Send first angle to server.
        delta1 = alpha - theta1 + (p1 + r1) * math.pi
        app_logger.log(f"Sending delta1 = {delta1}")
        send_meas_cmd(socket, delta1)
        m1 = recv_meas_outcome(socket)
        app_logger.log(f"Received m1 = {m1}")

        # Send second angle to server.
        delta2 = math.pow(-1, (m1 + r1)) * beta - theta2 + (p2 + r2) * math.pi
        app_logger.log(f"Sending delta2 = {delta2}")
        send_meas_cmd(socket, delta2)
        m2 = recv_meas_outcome(socket)
        app_logger.log(f"Received m2 = {m1}")

        return {
            "delta1": delta1 / math.pi,
            "delta2": delta2 / math.pi,
            "p1": p1,
            "p2": p2,
            "m1": m1,
            "m2": m2,
        }
