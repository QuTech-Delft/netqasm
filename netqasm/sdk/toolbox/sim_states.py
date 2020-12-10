from netqasm.runtime.settings import get_simulator, Simulator

if get_simulator() == Simulator.NETSQUID:
    import netsquid as ns
    from netsquid.qubits import operators


def qubit_from(phi, theta):
    """Only used for simulation output purposes.
    Uses the phi and theta angles to construct a NetSquid qubit."""
    if get_simulator() != Simulator.NETSQUID:
        raise RuntimeError("`qubit_from` function only possible with NetSquid simulator")

    q = ns.qubits.create_qubits(1)[0]
    rot_y = operators.create_rotation_op(theta, (0, 1, 0))
    rot_z = operators.create_rotation_op(phi, (0, 0, 1))
    ns.qubits.operate(q, rot_y)
    ns.qubits.operate(q, rot_z)
    return q


def to_dm(q):
    """Only used for simulation output purposes."""
    if get_simulator() != Simulator.NETSQUID:
        raise RuntimeError("`to_dm` function only possible with NetSquid simulator")

    return ns.qubits.reduced_dm(q)


def get_fidelity(q1, q2):
    """Only used for simulation output purposes.
    Gets the fidelity between the states q1 and q2"""
    if get_simulator() != Simulator.NETSQUID:
        raise RuntimeError("`get_fidelity` function only possible with NetSquid simulator")

    return q1.qstate.fidelity(q2)
