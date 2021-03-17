import numpy as np

from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.examples.lib.bqc import measXY, recv_teleported_state, recv_meas_cmd, send_meas_outcome

logger = get_netqasm_logger()


def main(app_config=None):
    socket = Socket("server", "client", log_config=app_config.log_config)
    epr_socket = EPRSocket("client")

    num_qubits = 4

    server = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
        max_qubits=num_qubits
    )

    with server:
        # Receive qubits q0 to q3 from the Client by teleportation.
        q = [None] * num_qubits
        for i in range(num_qubits):
            q[i] = recv_teleported_state(epr_socket)

        # Apply CPHASE gates between neighbouring nodes.
        # (See cluster state in the README.)
        for i in range(num_qubits - 1):
            q[i].cphase(q[i + 1])
        q[0].cphase(q[2])

        # TODO check why this is needed
        server.flush()

        # Receive from the Client the angle to measure q1 in.
        delta1 = recv_meas_cmd(socket)
        s1 = measXY(q[1], delta1)
        server.flush()
        send_meas_outcome(socket, s1)

        # Receive from the Client the angle to measure q2 in.
        delta2 = recv_meas_cmd(socket)
        s2 = measXY(q[2], delta2)
        server.flush()
        send_meas_outcome(socket, s2)

        # Measure the output qubits (q0 and q3) in the Y-basis.
        m0 = measXY(q[0], np.pi / 2)
        m1 = measXY(q[3], np.pi / 2)
        server.flush()

        # Send the measurement outcomes to the Client.
        send_meas_outcome(socket, m0)
        send_meas_outcome(socket, m1)
