from netqasm.logging.glob import set_log_level
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.qubit import Qubit


def main(no_output=False):
    with DebugConnection("Alice") as alice:
        num = 30000

        res = alice.new_array(init_values=[0]).get_future_index(0)

        with alice.loop(num):
            q = Qubit(alice)
            m = q.measure()
            res.add(m)

        if no_output:
            print(f"binary:\n{alice.storage[0]}")


if __name__ == "__main__":
    set_log_level("INFO")
    main()
