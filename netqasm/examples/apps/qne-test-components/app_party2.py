import math

from netqasm.sdk import Qubit, EPRSocket
from netqasm.sdk.external import NetQASMConnection, get_qubit_state, Socket
from netqasm.sdk.toolbox import set_qubit_state
from netqasm.logging.output import get_new_app_logger
from netqasm.sdk.classical_communication.message import StructuredMessage


def main(app_config=None):
    log_config = app_config.log_config
    app_logger = get_new_app_logger(app_name="party2", log_config=log_config)

    socket = Socket("party2", "party1", log_config=log_config)
    epr_socket = EPRSocket("party1")

    party2 = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket]
    )
    with party2:
        _epr1 = epr_socket.recv(1)[0]

        party2.flush()

        _simple_msg = socket.recv()
        _struct_msg = socket.recv_structured()

        _epr2 = epr_socket.recv(1)[0]


if __name__ == "__main__":
    main()
