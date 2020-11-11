from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.logging.glob import get_netqasm_logger

from shared.myfuncs import custom_send, custom_measure

logger = get_netqasm_logger()


def main(app_config=None):
    socket = Socket("alice", "bob", log_config=app_config.log_config)

    # Initialize the connection to the backend
    alice = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config
    )

    with alice:
        q1 = Qubit(alice)
        q1.measure()
        q2 = Qubit(alice)
        custom_measure(q2)

    socket.send("hello from main()")
    custom_send(socket)


if __name__ == "__main__":
    main()
