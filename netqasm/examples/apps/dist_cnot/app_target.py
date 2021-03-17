from netqasm.sdk import EPRSocket, Qubit
from netqasm.sdk.toolbox import set_qubit_state
from netqasm.sdk.external import NetQASMConnection, Socket


def main(app_config=None, phi=0.0, theta=0.0):
    # socket for creating an EPR pair with Controller
    controller_epr = EPRSocket("controller")

    # socket for communicating classical messages with Controller
    class_socket = Socket("target", "controller", log_config=app_config.log_config)

    # connect to the back-end
    target = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[controller_epr]
    )

    with target:
        # create one EPR pair with Controller
        epr = controller_epr.recv(1)[0]

        # initialize target qubit of the distributed CNOT
        target_qubit = Qubit(target)
        set_qubit_state(target_qubit, phi, theta)

        # let back-end execute the quantum operations above
        target.flush()

        # wait for Controller's measurement outcome
        m = class_socket.recv()

        # if outcome = 1, apply an X gate on the local EPR half
        if m == "1":
            epr.X()

        # At this point, `epr` is correlated with the control qubit on Controller's side.
        # (If Controller's control was in a superposition, `epr` is now entangled with it.)
        # Use `epr` as the control of a local CNOT on the target qubit.
        epr.cnot(target_qubit)

        # undo any potential entanglement between `epr` and Controller's control qubit
        epr.H()
        epr_meas = epr.measure()
        target.flush()

        # Controller will do a controlled-Z based on the outcome to undo the entanglement
        class_socket.send(str(epr_meas))

        # Wait for an ack before exiting
        assert class_socket.recv() == "ACK"

    return {
        'epr_meas': int(epr_meas)
    }
