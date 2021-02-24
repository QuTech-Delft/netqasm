import math

from netqasm.sdk import Qubit, EPRSocket
from netqasm.sdk.external import NetQASMConnection, get_qubit_state, Socket
from netqasm.sdk.toolbox import set_qubit_state
from netqasm.logging.output import get_new_app_logger
from netqasm.sdk.classical_communication.message import StructuredMessage


def main(app_config=None):
    log_config = app_config.log_config
    app_logger = get_new_app_logger(app_name="party1", log_config=log_config)

    socket = Socket("party1", "party2", log_config=log_config)
    epr_socket = EPRSocket("party2")

    party1 = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket]
    )
    with party1:
        app_logger.log("Starting with local gate operations")
        q1 = Qubit(party1)
        q1.X()
        q1.Y()
        q1.H()
        q1.Z()
        q1.rot_Z(angle=math.pi / 4)
        q1.rot_X(angle=(math.pi / 2))

        party1.flush()
        dm = get_qubit_state(q1)

        q2 = Qubit(party1)
        q1.cnot(q2)
        q2.cnot(q1)
        q1.cphase(q2)
        q2.cphase(q1)

        party1.flush()

        m1 = q1.measure()
        m2 = q2.measure()

        party1.flush()

        epr1 = epr_socket.create(1)[0]

        party1.flush()

        socket.send("This is a simple message. After this follows a message with header and payload.")
        msg = StructuredMessage(header="This is a header", payload="This is the payload")
        socket.send_structured(msg)
        app_logger.log(f"These classical messages and app logs should not remove the qubit state visualizations")

        epr2 = epr_socket.create(1)[0]
        epr1.cnot(epr2)

        app_logger.log(f"There should now be a 4-qubit group across two nodes")

    table_2_columns = []
    for i in range(10):
        table_2_columns.append(
            [i * 1, i * 2]
        )

    table_6_columns = []
    for i in range(10):
        table_6_columns.append(
            [f"some long text {i * 1000}", i, i + 1, i + 2, i + 3, f"even looooonger text {i * 11111111}"]
        )

    return {
        'm1': int(m1),
        'm2': int(m2),
        'state': dm.tolist(),
        'table2': table_2_columns,
        'table6': table_6_columns,
    }


if __name__ == "__main__":
    main()
