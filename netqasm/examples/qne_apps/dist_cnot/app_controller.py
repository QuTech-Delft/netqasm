import math

from numpy import linalg

from netqasm.logging.output import get_new_app_logger
from netqasm.runtime.settings import Simulator, get_simulator
from netqasm.sdk import EPRSocket, Qubit
from netqasm.sdk.external import NetQASMConnection, Socket, get_qubit_state
from netqasm.sdk.toolbox import set_qubit_state
from netqasm.sdk.toolbox.sim_states import qubit_from, to_dm


def main(app_config=None, phi=0.0, theta=0.0):
    # Inputs are coefficients of pi, e.g. phi=0.5 -> angle 0.5*pi
    phi *= math.pi
    theta *= math.pi

    log_config = app_config.log_config

    # socket for creating an EPR pair with target
    target_epr = EPRSocket("target")

    # socket for communicating classical messages with target
    class_socket = Socket("controller", "target", log_config=app_config.log_config)

    app_logger = get_new_app_logger(app_name="sender", log_config=log_config)

    # connect to the back-end
    controller = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[target_epr],
    )

    with controller:
        app_logger.log("Creating EPR pair with target...")
        # create one EPR pair with target
        epr = target_epr.create_keep(1)[0]

        # initialize control qubit of the distributed CNOT
        controller.flush()
        app_logger.log("Initializing control qubit...")
        ctrl_qubit = Qubit(controller)
        set_qubit_state(ctrl_qubit, phi, theta)
        controller.flush()
        app_logger.log("Initialized control qubit")

        # Synchronize with other nodes for cleaner logs/animations in QNE.
        class_socket.recv_silent()

        app_logger.log("Starting distributed CNOT...")
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
            app_logger.log("Outcome = 1, so doing Z correction")
            ctrl_qubit.Z()
        else:
            app_logger.log("Outcome = 0, no corrections needed")

        controller.flush()

        # ack the outcome
        class_socket.send_silent("ACK")

        # Get information about the final state. Only possible in simulation and
        # for visualizations purposes in QNE.
        if get_simulator() == Simulator.NETSQUID:
            original_dm = to_dm(qubit_from(phi, theta))
            final_dm = get_qubit_state(ctrl_qubit, reduced_dm=True)

            if linalg.matrix_rank(final_dm) != 1:
                entangled_text = (
                    "The controller's and target's qubits are entangled "
                    "so their individual states cannot be shown."
                )
            else:
                entangled_text = (
                    "The controller's and target's qubits are *not* "
                    "entangled. Their final states are displayed below."
                )
        else:
            original_dm = None
            final_dm = None
            entangled_text = ""

    return {
        "epr_meas": int(epr_meas),
        "original_state": original_dm.tolist(),
        "final_state": final_dm if final_dm is None else final_dm.tolist(),
        "entangled_text": entangled_text,
    }
