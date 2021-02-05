from netqasm.sdk import Qubit
from netqasm.runtime.app_config import default_app_config
from netqasm.sdk.external import NetQASMConnection, run_applications
from netqasm.logging.glob import get_netqasm_logger

logger = get_netqasm_logger()
inner_num = 10
outer_num = 8
inner_reg = "R0"
outer_reg = "R1"


def run_alice():
    with NetQASMConnection("Alice") as alice:

        array = alice.new_array(2, init_values=[0, 0])
        i = array.get_future_index(0)
        j = array.get_future_index(1)

        def outer_body(alice):
            def inner_body(alice):
                q = Qubit(alice)
                q.free()
                j.add(1)
            i.add(1)

            alice.loop_body(inner_body, inner_num, loop_register=inner_reg)
        alice.loop_body(outer_body, outer_num, loop_register=outer_reg)
    assert i == outer_num
    assert j == outer_num * inner_num


def test_nested_loop():
    run_applications([
        default_app_config("Alice", run_alice),
    ], use_app_config=False)
