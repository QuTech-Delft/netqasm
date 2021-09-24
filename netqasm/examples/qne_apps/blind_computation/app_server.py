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


def main(app_config=None):
    socket = Socket("server", "client", log_config=app_config.log_config)
    epr_socket = EPRSocket("client")

    server = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )

    with server:
        # Let client remotely prepare two qubits.
        q1 = recv_teleported_state(epr_socket)
        q2 = recv_teleported_state(epr_socket)

        server.flush()

        socket.recv_silent()

        # Apply a CPHASE gate between the two qubits.
        q1.cphase(q2)

        # TODO check why this is needed
        server.flush()

        # Receive from the client the angle to measure the first qubit in.
        angle = recv_meas_cmd(socket)
        s = measXY(q1, angle)
        server.flush()
        send_meas_outcome(socket, s)

        # Receive from the client the angle to measure the first qubit in.
        angle = recv_meas_cmd(socket)
        server.flush()
        q2.rot_Z(angle=angle)
        q2.H()
        server.flush()
        dm = get_qubit_state(q2)
        s = q2.measure()
        server.flush()
        send_meas_outcome(socket, s)

        return {"final_state": dm if dm is None else dm.tolist()}
