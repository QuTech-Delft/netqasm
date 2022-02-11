from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection
from netqasm.sdk.toolbox.measurements import parity_meas

logger = get_netqasm_logger()


def _get_default_strategy():
    return [
        ["XI", "-XZ", "IZ"],  # col 0
        ["XX", "YY", "ZZ"],  # col 1
        ["IX", "-ZX", "ZI"],  # col 2
    ]


def main(app_config=None, col=0, strategy=None):

    # Get the strategy
    if strategy is None:
        strategy = _get_default_strategy()
    if col >= len(strategy):
        raise ValueError(f"Not a col in the square {col}")

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("player1")

    # Initialize the connection
    player2 = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )
    with player2:
        # Create EPR pairs
        q1 = epr_socket.recv_keep()[0]
        q2 = epr_socket.recv_keep()[0]

        player2.flush()

        # Make sure we order the qubits consistently with Player1
        # Get entanglement IDs
        q1_ID = q1.entanglement_info.sequence_number
        q2_ID = q2.entanglement_info.sequence_number

        if int(q1_ID) < int(q2_ID):
            qb = q1
            qd = q2
        else:
            qb = q2
            qd = q1

        # Perform the three measurements
        m0, m1, m2 = (parity_meas([qb, qd], strategy[col][i]) for i in range(3))

    to_print = "\n\n"
    to_print += "==========================\n"
    to_print += "App player2: column is:\n"
    to_print += "(" + "_" * col + str(m0) + "_" * (2 - col) + ")\n"
    to_print += "(" + "_" * col + str(m1) + "_" * (2 - col) + ")\n"
    to_print += "(" + "_" * col + str(m2) + "_" * (2 - col) + ")\n"
    to_print += "==========================\n"
    to_print += "\n\n"
    logger.info(to_print)

    return {
        "col": [int(m0), int(m1), int(m2)],
    }


if __name__ == "__main__":
    main()
