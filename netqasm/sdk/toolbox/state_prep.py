from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

import numpy as np

from netqasm.lang.encoding import IMMEDIATE_BITS

if TYPE_CHECKING:
    from netqasm.sdk import qubit


def set_qubit_state(qubit: qubit.Qubit, phi: float = 0.0, theta: float = 0.0) -> None:
    r"""Assuming that the qubit is in the state :math:`|0\rangle`, this function
    rotates the state to :math:`\cos(\theta / 2)|0\rangle + e^{i\phi}\sin(\theta / 2)|1\rangle`.

    Parameters
    ----------
    qubit : :class:`.sdk.qubit.Qubit`
        The qubit to prepare the state.
    phi : float
        Angle around Z-axis from X-axis
    theta : float
        Angle from Z-axis
    """
    qubit.rot_Y(angle=theta)
    qubit.rot_Z(angle=phi)


def get_angle_spec_from_float(angle: float, tol: float = 1e-4) -> List[Tuple[int, int]]:
    r"""Tries to find the shortest sequence of (n, d) such that :math:`abs(\sum_i n_i \pi / 2 ^ {d_i} - angle) < tol`
    This is to find a sequence of rotations for a given angle.

    Parameters
    ----------
    angle : float
        The angle to approximate
    tol : float
        Tolerance to use
    """
    angle %= 2 * np.pi
    rest = angle / np.pi

    # Max value of `n`
    n_max = 2 ** IMMEDIATE_BITS - 1

    nds = []
    while rest > tol:
        # Find the largest `d` such that `rest <= n_max / 2 ^ d`
        d = int(np.floor(np.log2(n_max / rest)))
        # Find largest `n` such that `rest >= n / 2 ^ d`
        n = int(np.floor(rest * 2 ** d))
        # Shouldn't happen, but lets make sure
        assert n <= n_max, "Something went wrong, n is bigger than n_max"
        nds.append((n, d))
        rest -= n / 2 ** d

    # Check if some of the (n, d)'s can be simplified, i.e. if `n = b * 2 ^ m` for some `m` and `b`
    for i, (n, d) in enumerate(nds):
        n_new, d_new = n, d
        while (n_new % 2) == 0:
            n_new, d_new = (int(n_new / 2), d_new - 1)
        nds[i] = (n_new, d_new)
    nds = [(n, d) for (n, d) in nds if d < 32]
    return nds
