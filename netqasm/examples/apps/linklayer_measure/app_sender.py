from netqasm.sdk import Qubit, EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.sdk.toolbox import set_qubit_state
from netqasm.logging.output import get_new_app_logger
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.epr_socket import EPRType
from qlink_interface import RandomBasis
from netqasm.sdk.futures import Register


def main(app_config=None, phi=0., theta=0.):
    log_config = app_config.log_config
    app_logger = get_new_app_logger(app_name="sender", log_config=log_config)

    # Create a socket to send classical information
    socket = Socket("sender", "receiver", log_config=log_config)

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("receiver")

    # print("`sender` will start to teleport a qubit to `receiver`")

    # Initialize the connection to the backend
    sender = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket],
        return_arrays=False,
    )
    with sender:
        # Create a qubit to teleport
        q = Qubit(sender)
        set_qubit_state(q, phi, theta)

        # Create EPR pairs
        results = epr_socket.create(
            number=20, tp=EPRType.M, random_basis_local=RandomBasis.XZ)

        count = sender.new_register()

        for result in results:
            count.add(result.measurement_outcome)

        sender.flush()
        print(int(count))

        # Teleport
        # q.cnot(epr1)
        # q.H()
        # m1 = q.measure()
        # m2 = epr1.measure()

    # Send the correction information
    # m1, m2 = int(m1), int(m2)

    # app_logger.log(f"m1 = {m1}")
    # app_logger.log(f"m2 = {m2}")
    # print(f"`sender` measured the following teleportation corrections: m1 = {m1}, m2 = {m2}")
    # print("`sender` will send the corrections to `receiver`")

    # socket.send_structured(StructuredMessage("Corrections", (m1, m2)))

    # socket.send_silent(str((phi, theta)))

    # return {
    #     "m1": m1,
    #     "m2": m2
    # }


if __name__ == "__main__":
    main()
