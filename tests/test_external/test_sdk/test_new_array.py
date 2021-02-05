import random
from netqasm.sdk import Qubit
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging.glob import get_netqasm_logger

logger = get_netqasm_logger()


def run_alice():
    num = 10
    init_values = [random.randint(0, 1) for _ in range(num)]
    loop_register = "R0"

    with NetQASMConnection("Alice") as alice:
        array = alice.new_array(init_values=init_values)
        outcomes = alice.new_array(length=num)

        def body(alice):
            q = Qubit(alice)
            with array.get_future_index(loop_register).if_eq(1):
                q.X()
            q.measure(future=outcomes.get_future_index(loop_register))

        alice.loop_body(body, stop=num, loop_register=loop_register)
    outcomes = list(outcomes)
    logger.debug(f"outcomes: {outcomes}")
    logger.debug(f"init_values: {init_values}")
    assert outcomes == init_values


def test_new_array():
    run_applications([
        default_app_config("Alice", run_alice),
    ], use_app_config=False)
