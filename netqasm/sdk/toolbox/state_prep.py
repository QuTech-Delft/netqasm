def set_qubit_state(qubit, phi=0., theta=0.):
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
