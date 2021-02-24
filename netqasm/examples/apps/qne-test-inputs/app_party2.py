from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, get_qubit_state
from netqasm.sdk.toolbox import set_qubit_state


def main(
    app_config=None,
    i1: int = 0,
    i2: int = 0,
    f1: float = 0.0,
    f2: float = 0.0,
    b1: int = 0,  # bit (0 or 1)
    b2: int = 0,  # bit (0 or 1)
    range1: int = 0,  # [-10, 10]
    range2: int = 1,  # [1, 5]
    theta: float = 0.0,
    phi: float = 0.0,
    angle: float = 0.0,
    shared: int = 0,  # shared with other party, [0, 100]
):
    with NetQASMConnection("party2") as party2:
        q = Qubit(party2)
        set_qubit_state(q, phi, theta)
        party2.flush()

        dm = get_qubit_state(q)

    return {
        "i1": i1,
        "i2": i2,
        "f1": f1,
        "f2": f2,
        "b1": b1,
        "b2": b2,
        "range1": range1,
        "range2": range2,
        "theta": theta,
        "phi": phi,
        "qubit1": dm.tolist(),
        "angle": angle,
        "shared": shared,
    }


if __name__ == "__main__":
    main()
