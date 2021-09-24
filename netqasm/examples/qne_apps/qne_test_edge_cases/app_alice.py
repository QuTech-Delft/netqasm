from netqasm.sdk import EPRSocket, Qubit
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

    socket = Socket("alice", "david", log_config=log_config)

    alice = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket_bob, epr_socket_charlie],
    )

    with alice:
        epr_bob = epr_socket_bob.create(1)[0]
        alice.flush()

        epr_charlie = epr_socket_charlie.create(1)[0]
        alice.flush()

        epr_bob.cnot(epr_charlie)

        q = Qubit(alice)
        epr_bob.cnot(q)

        alice.flush()
        socket.send_silent("")


if __name__ == "__main__":
    main()
