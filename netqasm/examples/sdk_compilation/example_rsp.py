from netqasm.logging.glob import set_log_level
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.epr_socket import EPRSocket

DebugConnection.node_ids = {
    "Alice": 0,
    "Bob": 1,
}


def main(no_output=False):
    epr_socket = EPRSocket(remote_app_name="Bob")
    with DebugConnection("Alice", epr_sockets=[epr_socket]) as alice:
        m = epr_socket.create_rsp()[0]
        print(m.measurement_outcome)

    if no_output:
        # Third message since the first two are for init application
        # and opening the EPR socket
        print(f"binary:\n{alice.storage[2]}")


if __name__ == "__main__":
    set_log_level("INFO")
    main()
