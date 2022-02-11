import numpy as np

from netqasm.logging.output import get_new_app_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket


def measure_basis_0(bob, q):
    q.rot_Y(angle=-np.pi / 4)
    return q.measure()


def measure_basis_1(bob, q):
    q.rot_Y(angle=np.pi / 4)
    return q.measure()


def format_corrections(m1, m2):
    if (m1, m2) == (0, 0):
        return "No corrections"
    elif (m1, m2) == (0, 1):
        return "X"
    elif (m1, m2) == (1, 0):
        return "Z"
    elif (m1, m2) == (1, 1):
        return "X and Z"


def format_measurement_basis(y):
    if y == 0:
        return "Z-basis rotated around Y by pi / 4"
    elif y == 1:
        return "Z-basis rotated around Y by -pi / 4"


def game_won(x, y, a, b):
    if x == 1 and y == 1:
        if a != b:
            return "Alice and Bob won the game, since x * y = 1 and a ^ b = 1"
        else:
            return "Alice and Bob lost the game, since x * y = 1 and a ^ b = 0"
    else:
        if a == b:
            return "Alice and Bob won the game, since x * y = 0 and a ^ b = 0"
        else:
            return "Alice and Bob lost the game, since x * y = 0 and a ^ b = 1"


def main(app_config=None, y=0):
    if not (y == 0 or y == 1):
        raise ValueError(f"y should be 0 or 1, not {y}")

    app_logger = get_new_app_logger(
        app_name=app_config.app_name, log_config=app_config.log_config
    )

    # Only to enforce global order of operations for nice visualization,
    # NOT needed to obtain CHSH outcome correlations.
    socket_alice = Socket("bob", "alice", log_config=app_config.log_config)

    socket = Socket("bob", "repeater", log_config=app_config.log_config)
    epr_socket = EPRSocket("repeater")

    bob = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )

    with bob:
        # Wait for entanglement with Alice through repeater
        epr = epr_socket.recv_keep()[0]
        bob.flush()

        # Receive teleportation corrections
        msg = socket.recv()
        m1, m2 = eval(msg)
        app_logger.log(
            f"Applying teleportation corrections {format_corrections(m1, m2)}"
        )
        if m2 == 1:
            epr.X()
        if m1 == 1:
            epr.Z()
        bob.flush()

        # Tell Alice entanglement has been established
        socket_alice.send_silent("")

        # CHSH strategy: measure in one of 2 bases depending on y.
        app_logger.log(f"Measuring in basis y = {y}...")
        if y == 0:
            b = measure_basis_0(bob, epr)
        else:
            b = measure_basis_1(bob, epr)

    msg = socket_alice.recv_silent()
    x, a = eval(msg)

    app_logger.log(f"Bob outputs b = {b}")
    return {
        "b": int(b),
        "corrections": format_corrections(m1, m2),
        "basis": format_measurement_basis(y),
        "game_won": game_won(x, y, a, b),
    }


if __name__ == "__main__":
    main()
