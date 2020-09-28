from netqasm.sdk import EPRSocket, Qubit
from netqasm.sdk.toolbox import set_qubit_state
from netqasm.sdk.external import NetQASMConnection, Socket


def main(app_config=None, phi=0.0, theta=0.0):
    # socket for creating an EPR pair with Alice
    alice_epr = EPRSocket("alice")

    # socket for communicating classical messages with Alice
    class_socket = Socket("bob", "alice", log_config=app_config.log_config)

    # connect to the back-end
    bob = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[alice_epr]
    )

    with bob:
        # create one EPR pair with Alice
        epr = alice_epr.recv(1)[0]

        # initialize target qubit of the distributed CNOT
        target_qubit = Qubit(bob)
        set_qubit_state(target_qubit, phi, theta)

        # let back-end execute the quantum operations above
        bob.flush()

        # wait for Alice's measurement outcome
        m = class_socket.recv()

        # if outcome = 1, apply an X gate on the local EPR half
        if m == "1":
            epr.X()

        # At this point, `epr` is correlated with the control qubit on Alice's side.
        # (If Alice's control was in a superposition, `epr` is now entangled with it.)
        # Use `epr` as the control of a local CNOT on the target qubit.
        epr.cnot(target_qubit)

        # undo any potential entanglement between `epr` and Alice's control qubit
        epr.H()
        epr_meas = epr.measure()
        bob.flush()

        # Alice will do a controlled-Z based on the outcome to undo the entanglement
        class_socket.send(str(epr_meas))

        # Wait for an ack before exiting
        assert class_socket.recv() == "ACK"

    return {
        'epr_meas': int(epr_meas)
    }
