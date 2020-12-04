import netsquid as ns
from netsquid.qubits.qubit import Qubit as NsQubit
from netsquid.qubits import operators

from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket, get_qubit_state


def get_original(phi, theta) -> NsQubit:
    """Only used for simulation output purposes.
    Uses the original phi and theta values of the Sender (normally NOT known
    to the Receiver) to reconstruct the original state."""
    original = ns.qubits.create_qubits(1)[0]
    rot_y = operators.create_rotation_op(theta, (0, 1, 0))
    rot_z = operators.create_rotation_op(phi, (0, 0, 1))
    ns.qubits.operate(original, rot_y)
    ns.qubits.operate(original, rot_z)
    return original


def get_original_dm(original: NsQubit):
    """Only used for simulation output purposes."""
    return ns.qubits.reduced_dm(original)


def get_fidelity(original, dm):
    """Only used for simulation output purposes.
    Gets the fidelity between the original state and the received state"""
    return original.qstate.fidelity(dm)


def main(app_config=None):
    log_config = app_config.log_config

    # Create a socket to recv classical information
    socket = Socket("receiver", "sender", log_config=log_config)

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("sender")

    # Initialize the connection
    receiver = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket]
    )
    with receiver:
        epr = epr_socket.recv()[0]
        receiver.flush()

        # Get the corrections
        m1, m2 = socket.recv_structured().payload
        print(f"`receiver` got corrections: {m1}, {m2}")
        if m2 == 1:
            print("`receiver` will perform X correction")
            epr.X()
        if m1 == 1:
            print("`receiver` will perform Z correction")
            epr.Z()

        receiver.flush()
        # Get the qubit state
        # NOTE only possible in simulation, not part of actual application
        dm = get_qubit_state(epr)
        print(f"`receiver` recieved the teleported state {dm}")

        msg = socket.recv_silent()
        phi, theta = eval(msg)

        original = get_original(phi, theta)
        original_dm = get_original_dm(original)
        fidelity = get_fidelity(original, dm)

        return {
            "original_state": original_dm.tolist(),
            "correction1": "Z" if m1 == 1 else "None",
            "correction2": "X" if m2 == 1 else "None",
            "received_state": dm.tolist(),
            "fidelity": fidelity
        }


if __name__ == "__main__":
    main()
