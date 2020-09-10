import numpy as np


def bloch_sphere_rep(mat):
    """Computes polar coordinates in Bloch sphere given a single-qubit density matrix

    Parameters
    ----------
    mat : numpy.ndarray
        The single-qubit density matrix

    Returns
    -------
    tuple : (theta, phi, r)
    """
    assert isinstance(mat, np.ndarray), "mat should be instance of numpy.ndarray"
    assert mat.shape == (2, 2), "mat should be a 2x2 matrix"

    # Compute cartesian coordinates
    ax = (mat[0, 1] + mat[1, 0])
    ay = (mat[1, 0] - mat[0, 1]) / 1j
    az = 2 * mat[0, 0] - 1

    # Compute polar coordinates
    r = np.linalg.norm([ax, ay, az])
    assert r <= 1, "mat not normalized"
    if r == 0:
        return (0, 0, 0)
    theta = np.arccos(az / r)
    if theta in [0, np.pi]:
        return (theta, 0, r)
    phi = np.arccos(ax / r / np.sin(theta))
    if ay < 0:
        phi += np.pi

    return (theta, phi, r)
