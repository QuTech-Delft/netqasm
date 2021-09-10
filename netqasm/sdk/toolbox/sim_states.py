from __future__ import annotations

from netqasm.runtime.settings import Simulator, get_simulator

if get_simulator() == Simulator.NETSQUID:
    import netsquid as ns
    import numpy as np
    from netsquid.qubits import operators, qubitapi
    from netsquid.qubits.qubit import Qubit as NetSquidQubit


def qubit_from(phi: float, theta: float) -> NetSquidQubit:
    """Only used for simulation output purposes.
    Uses the phi and theta angles to construct a NetSquid qubit."""
    if get_simulator() != Simulator.NETSQUID:
        raise RuntimeError(
            "`qubit_from` function only possible with NetSquid simulator"
        )

    q = ns.qubits.create_qubits(1)[0]
    rot_y = operators.create_rotation_op(theta, (0, 1, 0))
    rot_z = operators.create_rotation_op(phi, (0, 0, 1))
    ns.qubits.operate(q, rot_y)
    ns.qubits.operate(q, rot_z)
    return q


def to_dm(q: NetSquidQubit) -> np.ndarray:
    """Only used for simulation output purposes."""
    if get_simulator() != Simulator.NETSQUID:
        raise RuntimeError("`to_dm` function only possible with NetSquid simulator")

    return ns.qubits.reduced_dm(q)


def get_fidelity(q1: NetSquidQubit, q2: np.ndarray) -> float:
    """Only used for simulation output purposes.
    Gets the fidelity between the states q1 and q2"""
    if get_simulator() != Simulator.NETSQUID:
        raise RuntimeError(
            "`get_fidelity` function only possible with NetSquid simulator"
        )

    return qubitapi.fidelity(q1, q2)  # type: ignore
