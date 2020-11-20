from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.qubit import Qubit
from netqasm.logging.glob import set_log_level


def main(no_output=False):
    with DebugConnection("Alice") as alice:
        num = 10

        outcomes = alice.new_array(num)
        even = alice.new_array(init_values=[0]).get_future_index(0)

        with alice.loop(num) as i:
            q = Qubit(alice)
            with even.if_eq(0):
                q.X()
            outcome = outcomes.get_future_index(i)
            q.measure(outcome)
            even.add(1, mod=2)

    if no_output:
        print(f'binary:\n{alice.storage[0]}')


if __name__ == "__main__":
    set_log_level('INFO')
    main()
