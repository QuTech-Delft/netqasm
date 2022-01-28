from netqasm.logging.output import get_new_app_logger
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket


def measure_basis_0(alice, q):
    return q.measure()


def measure_basis_1(alice, q):
    q.H()
    return q.measure()


def format_measurement_basis(x):
    if x == 0:
        return "Z-basis"
    elif x == 1:
        return "X-basis"


def main(app_config=None, x=0):
    if not (x == 0 or x == 1):
        raise ValueError(f"x should be 0 or 1, not {x}")

    # Only to enforce global order of operations for nice visualization,
    # NOT needed to obtain CHSH outcome correlations.
    socket_bob = Socket("alice", "bob", log_config=app_config.log_config)

    app_logger = get_new_app_logger(
        app_name=app_config.app_name, log_config=app_config.log_config
    )

    epr_socket = EPRSocket("repeater")

    alice = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )

    with alice:
        # Create EPR pair with Bob, through the repeater.
        epr = epr_socket.create_keep()[0]
        alice.flush()

        # Wait for Bob to receive entanglement through repeater.
        socket_bob.recv_silent()

        # CHSH strategy: measure in one of 2 bases depending on x.
        app_logger.log(f"Measuring in basis x = {x}...")
        if x == 0:
            a = measure_basis_0(alice, epr)
        else:
            a = measure_basis_1(alice, epr)

    # So that Bob can determine the outcome, purely for visualization purposes.
    socket_bob.send_silent(str((x, int(a))))

    app_logger.log(f"Alice outputs a = {a}")
    return {
        "a": int(a),
        "basis": format_measurement_basis(x),
    }


if __name__ == "__main__":
    main()
