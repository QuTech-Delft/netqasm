from netqasm.logging.glob import get_netqasm_logger
from netqasm.logging.output import get_new_app_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.sdk.toolbox.measurements import parity_meas

logger = get_netqasm_logger()


def _get_default_strategy():
    return [
        ["XI", "XX", "IX"],  # row 0
        ["-XZ", "YY", "-ZX"],  # row 1
        ["IZ", "ZZ", "ZI"],  # row 2
    ]


def main(app_config=None, row=0, strategy=None):
    # This socket is only for post-processing purposes and not needed for the strategy to work.
    socket = Socket("player1", "player2", log_config=app_config.log_config)

    app_logger = get_new_app_logger(
        app_name=app_config.app_name, log_config=app_config.log_config
    )

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
        app_logger.log("Creating shared state with other player...")
        # Create EPR pairs
        q1 = epr_socket.create_keep()[0]
        q2 = epr_socket.create_keep()[0]

        # TODO put in single subroutine?
        player1.flush()

        socket.send_silent("")

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
        app_logger.log(f"Measuring {strategy[row][0]} ...")
        m0 = parity_meas([qa, qc], strategy[row][0])
        player1.flush()
        app_logger.log(f"Outcome: {m0}")

        app_logger.log(f"Measuring {strategy[row][1]} ...")
        m1 = parity_meas([qa, qc], strategy[row][1])
        player1.flush()
        app_logger.log(f"Outcome: {m1}")

        app_logger.log(f"Measuring {strategy[row][2]} ...")
        m2 = parity_meas([qa, qc], strategy[row][2])
        player1.flush()
        app_logger.log(f"Outcome: {m2}")

        socket.send_silent("")

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

    # Only needed for visualization: to check at which cell the row intersects with the column of the other player.
    socket.send_silent(str(row))
    p1 = [int(m0), int(m1), int(m2)]
    socket.send_silent(str(p1))

    return {
        "row": [int(m0), int(m1), int(m2)],
    }


if __name__ == "__main__":
    main()
