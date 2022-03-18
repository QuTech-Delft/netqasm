from netqasm.lang.operand import Template
from netqasm.logging.glob import set_log_level
from netqasm.runtime.application import default_app_instance
from netqasm.sdk.external import NetQASMConnection, Socket, simulate_application
from netqasm.sdk.qubit import Qubit


def run_alice():
    socket = Socket("Alice", "Bob")

    with NetQASMConnection("Alice") as alice:
        # define variable that is known only at runtime
        # (namely when we receive it from Bob)
        angle = Template("angle_from_bob")

        q = Qubit(alice)
        q.rot_Z(n=angle, d=4)

        # compile subroutine but do not yet send to backend
        subroutine_template = alice.compile()
        assert subroutine_template is not None

        # contains an operand called `angle_from_bob` that does not have a concrete value
        print(subroutine_template)

        # receive the value from Bob
        angle = int(socket.recv())

        # instantiate subroutine with Bob's value
        subroutine = subroutine_template.instantiate(
            alice.app_id, arguments={"angle_from_bob": angle}
        )

        # send to backend
        alice.commit_subroutine(subroutine)


def run_bob():
    socket = Socket("Bob", "Alice")
    angle = 7  # in multiples of pi/16
    socket.send(str(angle))


if __name__ == "__main__":
    set_log_level("INFO")
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
            ("Bob", run_bob),
        ]
    )
    simulate_application(
        app_instance,
        use_app_config=False,
        enable_logging=True,
    )
