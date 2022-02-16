import random

from netqasm.logging.glob import get_netqasm_logger
from netqasm.runtime.application import default_app_instance
from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, simulate_application

logger = get_netqasm_logger()


def run_alice():
    num = 10
    init_values = [random.randint(0, 1) for _ in range(num)]
    loop_register = "R0"

    with NetQASMConnection("Alice") as alice:
        array = alice.new_array(init_values=init_values)
        outcomes = alice.new_array(length=num)

        def body(alice, _):
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
    app_instance = default_app_instance(
        [
            ("Alice", run_alice),
        ]
    )
    simulate_application(app_instance, use_app_config=False, enable_logging=False)
