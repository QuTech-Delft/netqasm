from netqasm.sdk.qubit import Qubit


def t_inverse(q: Qubit) -> None:
    """Performs an inverse of the T gate by applying the T gate 7 times."""
    for _ in range(7):
        q.T()


def toffoli_gate(control1: Qubit, control2: Qubit, target: Qubit) -> None:
    """Performs a Toffoli gate with `control1` and `control2` as control qubits
    and `target` as target, using CNOTS, Ts and Hadamard gates.

    See https://en.wikipedia.org/wiki/Toffoli_gate
    """
    target.H()
    control2.cnot(target)
    t_inverse(target)
    control1.cnot(target)
    target.T()
    control2.cnot(target)
    t_inverse(target)
    control1.cnot(target)
    control2.T()
    target.T()
    target.H()
    control1.cnot(control2)
    control1.T()
    t_inverse(control2)
    control1.cnot(control2)
