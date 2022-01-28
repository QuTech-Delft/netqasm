from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.external import NetQASMConnection


def main(app_config=None):
    log_config = app_config.log_config

    epr_socket = EPRSocket("client")

    server = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket],
        # return_arrays=False,
    )

    num_pairs = 10

    with server:
        outcomes = epr_socket.recv_measure(number=num_pairs)

    for outcome in outcomes:
        print(f"Server: {outcome.measurement_outcome}")


if __name__ == "__main__":
    main()
