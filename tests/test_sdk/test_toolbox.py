import pytest
import numpy as np

from netqasm.sdk.toolbox import get_angle_spec_from_float


@pytest.mark.parametrize('angle, tol, expected_nds', [
    (np.pi, 1e-6, [(1, 0)]),
    (np.pi / 2, 1e-6, [(1, 1)]),
    (np.pi / 1024, 1e-6, [(1, 10)]),
    (np.pi * (1 + 1 / 2 + 1 / 4 + 1 / 16), 1e-6, [(128 + 64 + 32 + 8, 7)]),
    (np.pi * (1 + 1 / 2 + 1 / 4 + 1 / 16 + 1 / 1024), 1e-6, [(232, 7), (1, 10)]),
    (np.pi / 3, 1e-6, None),
    (1.5, 1e-6, None),
])
def test(angle, tol, expected_nds):
    print(angle)
    nds = get_angle_spec_from_float(angle=angle, tol=tol)
    if expected_nds is not None:
        assert nds == expected_nds
    print(nds)
    approx = sum(n * np.pi / 2 ** d for n, d, in nds)
    print(approx)
    assert np.abs(approx - angle) < tol
