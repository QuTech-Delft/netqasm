from netqasm.sdk import EPRSocket, Qubit
from netqasm.sdk.toolbox import set_qubit_state
from netqasm.sdk.external import NetQASMConnection, Socket, get_qubit_state


def main(app_config=None, phi=0.0, theta=0.0):
    # socket for creating an EPR pair with target
    target_epr = EPRSocket("target")

    # socket for communicating classical messages with target
    class_socket = Socket("controller", "target", log_config=app_config.log_config)

    # connect to the back-end
    controller = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[target_epr]
    )

    with controller:
        # create one EPR pair with target
        epr = target_epr.create(1)[0]

        # initialize control qubit of the distributed CNOT
        ctrl_qubit = Qubit(controller)
        set_qubit_state(ctrl_qubit, phi, theta)

        # perform a local CNOT with `epr` and measure `epr`
        ctrl_qubit.cnot(epr)
        epr_meas = epr.measure()

        # let back-end execute the quantum operations above
        controller.flush()

        # send the outcome to target
        class_socket.send(str(epr_meas))

        # wait for target's measurement outcome to undo potential entanglement
        # between his EPR half and the original control qubit
        target_meas = class_socket.recv()
        if target_meas == "1":
            ctrl_qubit.Z()

        controller.flush()

        # ack the outcome
        class_socket.send("ACK")

        # get the combined state of Controller's control and target's target
        dm = get_qubit_state(ctrl_qubit, reduced_dm=False)

        return {
            'epr_meas': int(epr_meas),
            'final_state': dm if dm is None else dm.tolist(),
        }
