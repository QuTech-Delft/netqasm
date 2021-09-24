from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket


def main(app_config=None):
    log_config = app_config.log_config

    socket = Socket("party2", "party1", log_config=log_config)
    epr_socket = EPRSocket("party1")

    party2 = NetQASMConnection(
        app_name=app_config.app_name, log_config=log_config, epr_sockets=[epr_socket]
    )
    with party2:
        _ = epr_socket.recv(1)[0]

        party2.flush()

        _ = socket.recv()
        _ = socket.recv_structured()

        _ = epr_socket.recv(1)[0]


if __name__ == "__main__":
    main()
