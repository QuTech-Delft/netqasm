from typing import List, Union

from netqasm.sdk.futures import Future, RegFuture
from netqasm.sdk.qubit import Qubit


def parity_meas(qubits: List[Qubit], bases: str) -> Union[Future, RegFuture, int]:
    """
    Performs a parity measurement on the provided qubits in the Pauli bases specified by 'bases'.
    `bases` should be a string with letters in 'IXYZ' and optionally start with '-'.
    If `bases` starts with '-', then the measurement outcome is flipped.
    The `basis` should have the same length as the number of qubits provided or +1 if starts with '-'.
    If more than one letter of 'bases' is not identity, then an ancilla qubit will be used, which is created
    using the connection of the first qubit.

    Parameters
    ----------
    qubits : List[:class:`~.sdk.qubit.Qubit`]
        The qubits to measure
    bases : str
        What parity meas to perform.

    Returns
    -------
    :class:~.sdk.futures.Future
        The measurement outcome
    """

    if bases.startswith("-"):
        negative = True
        bases = bases[1:]
    else:
        negative = False
    if not (len(qubits) == len(bases)):
        raise ValueError("Number of bases needs to be the number of qubits.")
    if not all([(B in "IXYZ") for B in bases]):
        raise ValueError("All elements of bases need to be in 'IXYZ'.")

    num_qubits = len(qubits)

    flip_basis = ["I"] * num_qubits
    non_identity_bases = []

    # declare outcome variable
    m: Union[Future, RegFuture, int]

    # Check if we need to flip the bases of the qubits
    for i in range(len(bases)):
        B = bases[i]
        if B == "X":
            flip_basis[i] = "H"
            non_identity_bases.append(i)
        elif B == "Y":
            flip_basis[i] = "K"
            non_identity_bases.append(i)
        elif B == "Z":
            non_identity_bases.append(i)
        else:
            pass

    if len(non_identity_bases) == 0:
        # Trivial measurement
        m = 0

    elif len(non_identity_bases) == 1:
        # Single_qubit measurement
        q_index = non_identity_bases[0]
        q = qubits[q_index]

        # Flip to correct basis
        if flip_basis[q_index] == "H":
            q.H()
        if flip_basis[q_index] == "K":
            q.K()

        # m = q.measure()
        m = q.measure(inplace=True)

        # # Flip the qubit back
        if flip_basis[q_index] == "H":
            q.H()
        if flip_basis[q_index] == "K":
            q.K()

    else:
        # Parity measurement, ancilla needed

        # Use the connection of the first qubit
        conn = qubits[0]._conn

        # Initialize ancilla qubit
        anc = Qubit(conn)

        # Flip to correct basis
        for i in range(len(bases)):
            if flip_basis[i] == "H":
                qubits[i].H()
            if flip_basis[i] == "K":
                qubits[i].K()

        # Transfer parity information to ancilla qubit
        for i in non_identity_bases:
            qubits[i].cnot(anc)

        # Measure ancilla qubit
        m = anc.measure()

        # Flip to correct basis
        for i in range(len(bases)):
            if flip_basis[i] == "H":
                qubits[i].H()
            if flip_basis[i] == "K":
                qubits[i].K()
    if negative:
        if not isinstance(m, Future):
            assert isinstance(m, int)
            m = 1 - m
        else:
            m.add(1, mod=2)
    return m
