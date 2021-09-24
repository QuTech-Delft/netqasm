from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket


def main(
    app_config=None,
):
    log_config = app_config.log_config

    #       alice
    # bob           charlie
    #       david

    epr_socket_alice = EPRSocket("alice")
    epr_socket_david = EPRSocket("david")

    socket = Socket("charlie", "bob", log_config=log_config)

    charlie = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket_alice, epr_socket_david],
    )

    with charlie:
        epr_alice = epr_socket_alice.recv(1)[0]
        charlie.flush()

        epr_david = epr_socket_david.recv(1)[0]
        charlie.flush()

        epr_alice.cnot(epr_david)

        charlie.flush()
        socket.recv_silent()

        # q = Qubit(charlie)
        # epr_alice.cnot(q)

        socket.send("0123456789")
        socket.send("0123456789 123456789")
        socket.send("0123456789 123456789 123456789")
        socket.send("0123456789 123456789 123456789 123456789")
        socket.send("0123456789 123456789 123456789 123456789 123456789")
        socket.send("0123456789 123456789 123456789 123456789 123456789 123456789")
        socket.send(
            "0123456789 123456789 123456789 123456789 123456789 123456789 123456789"
        )

        socket.send_silent("")


if __name__ == "__main__":
    main()
