from netqasm.sdk import EPRSocket
from netqasm.logging.output import get_new_app_logger
from netqasm.sdk.external import NetQASMConnection


def measure_basis_0(alice, q):
    return q.measure()


def measure_basis_1(alice, q):
    q.H()
    return q.measure()


def main(app_config=None, x=0):
    if not (x == 0 or x == 1):
        raise ValueError(f"x should be 0 or 1, not {x}")

    app_logger = get_new_app_logger(
        app_name=app_config.app_name,
        log_config=app_config.log_config
    )
    app_logger.log(f"Alice received input bit x = {x}")

    epr_socket = EPRSocket("repeater")

    alice = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket]
    )

    with alice:
        # Create EPR pair with Bob, through the repeater.
        epr = epr_socket.create()[0]

        # CHSH strategy: measure in one of 2 bases depending on x.
        if x == 0:
            a = measure_basis_0(alice, epr)
        else:
            a = measure_basis_1(alice, epr)

    app_logger.log(f"Alice outputs a = {a}")
    return {'a': int(a)}


if __name__ == "__main__":
    main()
