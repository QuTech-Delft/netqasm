from shared.myfuncs import custom_measure, custom_recv

from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, Socket

logger = get_netqasm_logger()


def main(app_config=None):
    socket = Socket("bob", "alice", log_config=app_config.log_config)

    # Initialize the connection to the backend
    bob = NetQASMConnection(
        app_name=app_config.app_name, log_config=app_config.log_config
    )
    with bob:
        q = Qubit(bob)
        custom_measure(q)

    socket.recv()
    custom_recv(socket)


if __name__ == "__main__":
    main()
