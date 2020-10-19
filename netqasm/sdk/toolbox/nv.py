import numpy as np


def get_nv_numerator_from_float(angle, tol=1e-3):
    r"""Tries to find a value k such that `angle` = k * pi/16. Raises a `ValueError` if no k can be found close enough
    """
    k = int(round(angle * 16 / np.pi))
    if abs((k * np.pi / 16) - angle) > tol:
        raise ValueError(f"Cannot find `k` such that angle {angle} = k * pi / 16.")
    k %= 32
    return k
