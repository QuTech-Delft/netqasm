from netqasm.logging.output import get_new_app_logger
from netqasm.runtime.settings import Simulator, get_simulator
from netqasm.sdk import EPRSocket, Qubit
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.sdk.toolbox import set_qubit_state


def main(app_config=None, phi=0.0, theta=0.0):
    log_config = app_config.log_config
    app_logger = get_new_app_logger(app_name="sender", log_config=log_config)

    # Create a socket to send classical information
    socket = Socket("sender", "receiver", log_config=log_config)

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("receiver")

    print("`sender` will start to teleport a qubit to `receiver`")

    # Initialize the connection to the backend
    sender = NetQASMConnection(
        app_name=app_config.app_name, log_config=log_config, epr_sockets=[epr_socket]
    )
    with sender:
        # Create a qubit to teleport
        q = Qubit(sender)
        set_qubit_state(q, phi, theta)

        # Create EPR pairs
        epr = epr_socket.create_keep()[0]

        # Teleport
        q.cnot(epr)
        q.H()
        m1 = q.measure()
        m2 = epr.measure()

    # Send the correction information
    m1, m2 = int(m1), int(m2)

    app_logger.log(f"m1 = {m1}")
    app_logger.log(f"m2 = {m2}")
    print(
        f"`sender` measured the following teleportation corrections: m1 = {m1}, m2 = {m2}"
    )
    print("`sender` will send the corrections to `receiver`")

    socket.send_structured(StructuredMessage("Corrections", (m1, m2)))

    if get_simulator() == Simulator.NETSQUID:
        socket.send_silent(str((phi, theta)))

    return {"m1": m1, "m2": m2}


if __name__ == "__main__":
    main()
