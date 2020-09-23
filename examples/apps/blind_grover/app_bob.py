import numpy as np

from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket
from examples.lib.bqc import measXY, recv_teleported_state, recv_meas_cmd, send_meas_outcome

logger = get_netqasm_logger()


def main(app_config=None):
    socket = Socket("bob", "alice", log_config=app_config.log_config)
    epr_socket = EPRSocket("alice")

    num_qubits = 4

    node_name = app_config.node_name
    if node_name is None:
        node_name = app_config.app_name

    bob = NetQASMConnection(
        node_name=node_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
        max_qubits=num_qubits
    )

    with bob:
        # Receive qubits q0 to q3 from Alice by teleportation.
        q = [None] * num_qubits
        for i in range(num_qubits):
            q[i] = recv_teleported_state(epr_socket)

        # Apply CPHASE gates between neighbouring nodes.
        # (See cluster state in the README.)
        for i in range(num_qubits - 1):
            q[i].cphase(q[i + 1])
        q[0].cphase(q[2])

        # Receive from Alice the angle to measure q1 in.
        delta1 = recv_meas_cmd(socket)
        s1 = measXY(q[1], delta1)
        bob.flush()
        send_meas_outcome(socket, s1)

        # Receive from Alice the angle to measure q2 in.
        delta2 = recv_meas_cmd(socket)
        s2 = measXY(q[2], delta2)
        bob.flush()
        send_meas_outcome(socket, s2)

        # Measure the output qubits (q0 and q3) in the Y-basis.
        m0 = measXY(q[0], np.pi / 2)
        m1 = measXY(q[3], np.pi / 2)
        bob.flush()

        # Send the measurement outcomes to Alice.
        send_meas_outcome(socket, m0)
        send_meas_outcome(socket, m1)
