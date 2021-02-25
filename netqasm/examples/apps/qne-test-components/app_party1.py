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
        app_logger.log("Starting with local gate operations: init, X, H, Z, RotZ(pi/4), RotX(pi/2)")
        q0 = Qubit(party1)
        party1.flush()
        dm_ket_0 = get_qubit_state(q0)

        q0.X()
        party1.flush()
        dm_ket_1 = get_qubit_state(q0)

        q0.H()
        party1.flush()
        dm_ket_minus = get_qubit_state(q0)

        q0.Z()
        party1.flush()
        dm_ket_plus = get_qubit_state(q0)

        q0.rot_Z(angle=math.pi / 4)
        party1.flush()
        dm_ket_plus_pi4 = get_qubit_state(q0)

        q0.rot_X(angle=(math.pi / 2))

        party1.flush()
        app_logger.log("Following gates: init qubit 1, CNOT(0, 1), CNOT(1, 0), CPHASE(0, 1), CPHASE(1, 0)")

        q1 = Qubit(party1)
        q0.cnot(q1)
        q1.cnot(q0)
        q0.cphase(q1)
        q1.cphase(q0)

        party1.flush()
        app_logger.log("Following gates: init qubit 2, CNOT(0, 2), CNOT(2, 0)")

        q2 = Qubit(party1)
        q0.cnot(q2)
        q2.cnot(q0)

        party1.flush()
        app_logger.log("Following gates: measure qubit 2, measure qubit 0, measure qubit 1")

        m2 = q2.measure()
        m0 = q0.measure()
        m1 = q1.measure()

        party1.flush()
        app_logger.log("Following operation: create entanglement")

        epr1 = epr_socket.create(1)[0]

        party1.flush()

        socket.send("This is a simple message. After this follows a message with header and payload.")
        msg = StructuredMessage(header="This is a header", payload="This is the payload")
        socket.send_structured(msg)
        app_logger.log(f"These classical messages and app logs should not remove the qubit state visualizations")

        party1.flush()
        app_logger.log("Following operation: create entanglement")

        epr2 = epr_socket.create(1)[0]

        party1.flush()
        app_logger.log("Following operation: CNOT(0, 1). After that, there should be a 4-qubit group across two nodes")
        epr1.cnot(epr2)

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
        'm0': int(m0),
        'm1': int(m1),
        'm2': int(m2),
        'v1': 42,
        'v2': -17,
        'v3': "Hello",
        'state_0': dm_ket_0.tolist(),
        'state_1': dm_ket_1.tolist(),
        'state_plus': dm_ket_plus.tolist(),
        'state_minus': dm_ket_minus.tolist(),
        'state_plus_pi4': dm_ket_plus_pi4.tolist(),
        'table2': table_2_columns,
        'table6': table_6_columns,
    }


if __name__ == "__main__":
    main()
