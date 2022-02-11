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


def main(app_config=None, y=0):
    if not (y == 0 or y == 1):
        raise ValueError(f"y should be 0 or 1, not {y}")

    app_logger = get_new_app_logger(
        app_name=app_config.app_name, log_config=app_config.log_config
    )
    app_logger.log(f"Bob received input bit y = {y}")

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
        app_logger.log(f"Bob got teleportation corrections: {msg}")
        m1, m2 = eval(msg)
        if m2 == 1:
            epr.X()
        if m1 == 1:
            epr.Z()

        # CHSH strategy: measure in one of 2 bases depending on y.
        if y == 0:
            b = measure_basis_0(bob, epr)
        else:
            b = measure_basis_1(bob, epr)

    app_logger.log(f"Bob outputs b = {b}")
    return {"b": int(b)}


if __name__ == "__main__":
    main()
