from netqasm.sdk import Qubit, EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.sdk.toolbox import set_qubit_state
from netqasm.logging.output import get_new_app_logger
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.epr_socket import EPRType
from qlink_interface import RandomBasis
from netqasm.sdk.futures import Register


def main(app_config=None, phi=0., theta=0.):
    log_config = app_config.log_config

    epr_socket = EPRSocket("receiver")

    sender = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket],
        return_arrays=False,
    )
    with sender:
        num_pairs = 10
        outcomes = sender.new_array(num_pairs)
        ones_count = sender.new_register()

        def post_create(conn, q, pair):
            outcome = outcomes.get_future_index(pair)
            m = q.measure(outcome)
            ones_count.add(m)

        # Create EPR pair
        epr_socket.create(
            number=num_pairs,
            tp=EPRType.K,
            sequential=True,
            post_routine=post_create,
        )

    print(ones_count)


if __name__ == "__main__":
    main()
