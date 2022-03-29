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
        q.rot_X(n=angle, d=4)
        m = q.measure()

        # compile subroutine but do not yet send to backend
        subroutine = alice.compile()
        assert subroutine is not None

        # contains an operand called `angle_from_bob` that does not have a concrete value
        print(subroutine)

        # receive the value from Bob
        angle = int(socket.recv())

        # instantiate subroutine with Bob's value
        subroutine.instantiate(alice.app_id, arguments={"angle_from_bob": angle})

        # send to backend
        alice.commit_subroutine(subroutine)

        # alice should have done an X-rotation of angle pi -> qubit must be |1>
        assert int(m) == 1


def run_bob():
    socket = Socket("Bob", "Alice")
    angle = 16  # in multiples of pi/16
    socket.send(str(angle))


def test_precompilation():
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
        enable_logging=False,
    )


if __name__ == "__main__":
    test_precompilation()
