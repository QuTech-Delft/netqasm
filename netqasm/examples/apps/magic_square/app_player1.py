from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection
from netqasm.sdk.toolbox.measurements import parity_meas

logger = get_netqasm_logger()


def _get_default_strategy():
    return [
        ["XI", "XX", "IX"],  # row 0
        ["-XZ", "YY", "-ZX"],  # row 1
        ["IZ", "ZZ", "ZI"],  # row 2
    ]


def main(app_config=None, row=0, strategy=None):

    if strategy is None:
        strategy = _get_default_strategy()
    if row >= len(strategy):
        raise ValueError(f"Not a row in the square {row}")

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("player2")

    # Initialize the connection
    player1 = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )
    with player1:
        # Create EPR pairs
        q1 = epr_socket.create_keep()[0]
        q2 = epr_socket.create_keep()[0]

        # TODO put in single subroutine?
        player1.flush()

        # Make sure we order the qubits consistently with player2
        # Get entanglement IDs
        q1_ID = q1.entanglement_info.sequence_number
        q2_ID = q2.entanglement_info.sequence_number

        if int(q1_ID) < int(q2_ID):
            qa = q1
            qc = q2
        else:
            qa = q2
            qc = q1

        # Perform the three measurements
        m0, m1, m2 = (parity_meas([qa, qc], strategy[row][i]) for i in range(3))

    to_print = "\n\n"
    to_print += "==========================\n"
    to_print += "App player1: row is:\n"
    for _ in range(row):
        to_print += "(___)\n"
    to_print += f"({m0}{m1}{m2})\n"
    for _ in range(2 - row):
        to_print += "(___)\n"
    to_print += "==========================\n"
    to_print += "\n\n"
    logger.info(to_print)

    return {
        "row": [int(m0), int(m1), int(m2)],
    }


if __name__ == "__main__":
    main()
