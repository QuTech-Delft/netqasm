from netqasm.examples.lib.bqc import (
    measXY,
    recv_meas_cmd,
    recv_teleported_state,
    send_meas_outcome,
)
from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket, get_qubit_state

logger = get_netqasm_logger()


def main(app_config=None, num_iter=3):
    socket = Socket("server", "client", log_config=app_config.log_config)
    epr_socket = EPRSocket("client")

    num_qubits = num_iter + 1

    server = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
        max_qubits=num_qubits,
    )

    with server:
        # Receive qubits q[0] to q[num_qubits - 1] from the Client by teleportation.
        q = [None] * num_qubits
        for i in range(num_qubits):
            q[i] = recv_teleported_state(epr_socket)

        # Apply a CPHASE gate between every pair of consecutive qubits.
        for i in range(num_qubits - 1):
            q[i].cphase(q[i + 1])

        # TODO check why this is needed
        server.flush()

        # Main loop. Receive from the Client the angle to measure q[i] in.
        for i in range(num_iter):
            angle = recv_meas_cmd(socket)
            s = measXY(q[i], angle)
            server.flush()
            send_meas_outcome(socket, s)

        # The output of the computation is in the last qubit.
        dm = get_qubit_state(q[num_qubits - 1])
        return {"output_state": dm if dm is None else dm.tolist()}
