from netqasm.logging.glob import get_netqasm_logger
from netqasm.logging.output import get_new_app_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.sdk.toolbox.measurements import parity_meas

logger = get_netqasm_logger()


def _get_default_strategy():
    return [
        ["XI", "-XZ", "IZ"],  # col 0
        ["XX", "YY", "ZZ"],  # col 1
        ["IX", "-ZX", "ZI"],  # col 2
    ]


def main(app_config=None, col=0, strategy=None):
    # This socket is only for post-processing purposes and not needed for the strategy to work.
    socket = Socket("player2", "player1", log_config=app_config.log_config)

    app_logger = get_new_app_logger(
        app_name=app_config.app_name, log_config=app_config.log_config
    )

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

        socket.recv_silent()

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

        # Wait for player 1 to finish their measurements
        socket.recv_silent()

        # Perform the three measurements
        app_logger.log(f"Measuring {strategy[col][0]} ...")
        m0 = parity_meas([qb, qd], strategy[col][0])
        player2.flush()
        app_logger.log(f"Outcome: {m0}")

        app_logger.log(f"Measuring {strategy[col][1]} ...")
        m1 = parity_meas([qb, qd], strategy[col][1])
        player2.flush()
        app_logger.log(f"Outcome: {m1}")

        app_logger.log(f"Measuring {strategy[col][2]} ...")
        m2 = parity_meas([qb, qd], strategy[col][2])
        player2.flush()
        app_logger.log(f"Outcome: {m2}")

    to_print = "\n\n"
    to_print += "==========================\n"
    to_print += "App player2: column is:\n"
    to_print += "(" + "_" * col + str(m0) + "_" * (2 - col) + ")\n"
    to_print += "(" + "_" * col + str(m1) + "_" * (2 - col) + ")\n"
    to_print += "(" + "_" * col + str(m2) + "_" * (2 - col) + ")\n"
    to_print += "==========================\n"
    to_print += "\n\n"
    logger.info(to_print)

    # Only needed for visualization: to check at which cell the column intersects with the row of the other player.
    player1_row = eval(socket.recv_silent())
    player1_outcomes = eval(socket.recv_silent())
    col_outcomes = [int(m0), int(m1), int(m2)]

    square = [["", "", ""], ["", "", ""], ["", "", ""]]

    square[player1_row][0] = str(player1_outcomes[0])
    square[player1_row][1] = str(player1_outcomes[1])
    square[player1_row][2] = str(player1_outcomes[2])
    square[0][col] = str(col_outcomes[0])
    square[1][col] = str(col_outcomes[1])
    square[2][col] = str(col_outcomes[2])
    square[player1_row][col] = f"{player1_outcomes[col]}/{col_outcomes[player1_row]}"

    # table = []
    # for row in range(3):
    #     table.append(
    #         square[row]
    #     )

    return {
        "col": col_outcomes,
        "square": square,
    }


if __name__ == "__main__":
    main()
