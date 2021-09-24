from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, get_qubit_state
from netqasm.sdk.toolbox import set_qubit_state

from .conf import apps
from .sub_protocols import quantum_anonymous_tranmission, setup_sockets

logger = get_netqasm_logger()


def anonymous_transmission(
    app_name,
    app_config=None,
    sender=False,
    receiver=False,
    phi=None,
    theta=None,
):

    # Setup sockets, epr_sockets and a broadcast_channel needed for the protocol
    sockets = setup_sockets(
        app_name=app_config.app_name,
        apps=apps,
        log_config=app_config.log_config,
    )

    # Initialize the connection to the backend
    conn = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=sockets.epr_sockets,
    )
    with conn:
        if sender:
            # Prepare the qubit to teleport
            qubit = Qubit(conn)
            set_qubit_state(qubit=qubit, phi=phi, theta=theta)
        else:
            qubit = None
        q = quantum_anonymous_tranmission(
            conn=conn,
            sockets=sockets,
            num_nodes=len(apps),
            sender=sender,
            receiver=receiver,
            qubit=qubit,
        )
        if receiver:
            dm = get_qubit_state(q)
            output = {"qubit_state": dm.tolist()}
        else:
            output = None
    return output
