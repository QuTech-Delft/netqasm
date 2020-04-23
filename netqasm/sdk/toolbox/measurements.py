from netqasm.sdk import Qubit as qubit


def parity_meas(qubits, bases, node, negative=False):
    """
    Performs a parity measurement on the provided qubits in the Pauli bases specified by 'bases'.
    'bases' should be a string with letters in "IXYZ" and have the same length as the number of qubits provided.
    If 'negative' is true the measurement outcome is flipped.
    If more than one letter of 'bases' is not identity, then an ancilla qubit will be used, which is created
    using the provided 'node'.

    # TODO update params
    :param qubits: List of qubits to be measured.
    :param bases: String specifying the Pauli-bases of the measurement. Example bases="IXY" for three qubits.
    :type bases: str
    :param node: The node storing the qubits. Used for creating an ancilla qubit.
    :type node: :obj: `SimulaQron.cqc.pythonLib.cqc.CQCConnection`
    :param negative: If the measurement outcome should be flipped or not.
    :type negative: bool
    :return: The measurement outcome 0 or 1, where 0 correspond to the +1 eigenvalue of the measurement operator.
    """

    if not (len(qubits) == len(bases)):
        raise ValueError("Number of bases needs to be the number of qubits.")
    if not all([(B in "IXYZ") for B in bases]):
        raise ValueError("All elements of bases need to be in 'IXYZ'.")

    num_qubits = len(qubits)

    flip_basis = ["I"]*num_qubits
    non_identity_bases = []

    # Check if we need to flip the bases of the qubits
    for i in range(len(bases)):
        B = bases[i]
        if B == 'X':
            flip_basis[i] = "H"
            non_identity_bases.append(i)
        elif B == 'Y':
            flip_basis[i] = "K"
            non_identity_bases.append(i)
        elif B == 'Z':
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
        if flip_basis[q_index] == 'H':
            q.H()
        if flip_basis[q_index] == 'K':
            q.K()

        # m = q.measure()
        m = q.measure(inplace=True)

        # # Flip the qubit back
        if flip_basis[q_index] == 'H':
            q.H()
        if flip_basis[q_index] == 'K':
            q.K()

    else:
        # Parity measurement, ancilla needed

        # Initialize ancilla qubit
        anc = qubit(node)

        # Flip to correct basis
        for i in range(len(bases)):
            if flip_basis[i] == 'H':
                qubits[i].H()
            if flip_basis[i] == 'K':
                qubits[i].K()

        # Transfer parity information to ancilla qubit
        for i in non_identity_bases:
            qubits[i].cnot(anc)

        # Measure ancilla qubit
        m = anc.measure()

        # Flip to correct basis
        for i in range(len(bases)):
            if flip_basis[i] == 'H':
                qubits[i].H()
            if flip_basis[i] == 'K':
                qubits[i].K()
    if negative:
        m.add(1, mod=2)
    return m
