from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket


def main(
    app_config=None,
):
    log_config = app_config.log_config

    #       alice
    # bob           charlie
    #       david

    epr_socket_bob = EPRSocket("bob")
    epr_socket_charlie = EPRSocket("charlie")

    socket = Socket("david", "alice", log_config=log_config)

    david = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket_bob, epr_socket_charlie]
    )

    with david:
        socket.recv_silent()

        epr_bob = epr_socket_bob.create(1)[0]
        david.flush()

        epr_charlie = epr_socket_charlie.create(1)[0]
        david.flush()

        epr_bob.cnot(epr_charlie)

        # q = Qubit(david)
        # epr_bob.cnot(q)


if __name__ == "__main__":
    main()
