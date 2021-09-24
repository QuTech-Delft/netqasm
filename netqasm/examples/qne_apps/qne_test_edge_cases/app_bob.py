from netqasm.sdk import EPRSocket, Qubit
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

    socket = Socket("bob", "charlie", log_config=log_config)

    bob = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket_alice, epr_socket_david],
    )

    with bob:
        epr_alice = epr_socket_alice.recv(1)[0]
        bob.flush()

        epr_david = epr_socket_david.recv(1)[0]
        bob.flush()

        epr_alice.cnot(epr_david)

        q = Qubit(bob)
        epr_alice.cnot(q)

        bob.flush()
        socket.send_silent("")

        socket.recv_silent()


if __name__ == "__main__":
    main()
