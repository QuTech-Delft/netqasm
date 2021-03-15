import numpy as np
import pytest

from netqasm.util.states import bloch_sphere_rep


@pytest.mark.parametrize(
    "mat, expected",
    [
        (np.array([[1, 0], [0, 0]]), (0, 0, 1)),  # |0>
        (np.array([[0, 0], [0, 1]]), (np.pi, 0, 1)),  # |1>
        (np.array([[1, 1], [1, 1]]) / 2, (np.pi / 2, 0, 1)),  # |+>
        (np.array([[1, -1], [-1, 1]]) / 2, (np.pi / 2, np.pi, 1)),  # |->
        (
            np.array([[1, -1j], [1j, 1]]) / 2,
            (np.pi / 2, np.pi / 2, 1),
        ),  # (|0>+j|1>) / sqrt(2)
        (
            np.array([[1, 1j], [-1j, 1]]) / 2,
            (np.pi / 2, 3 * np.pi / 2, 1),
        ),  # (|0>-j|1>) / sqrt(2)
        (np.array([[1, 0], [0, 1]]) / 2, (0, 0, 0)),  # maximally mixed
        (
            np.array(
                [
                    [1 + 1 / np.sqrt(2), (1 - 1j) / 2],
                    [(1 + 1j) / 2, 1 - 1 / np.sqrt(2)],
                ]
            )
            / 2,
            (np.pi / 4, np.pi / 4, 1),
        ),
        (
            np.array(
                [
                    [1 + 1 / (2 * np.sqrt(2)), (1 - 1j) / 4],
                    [(1 + 1j) / 4, 1 - 1 / (2 * np.sqrt(2))],
                ]
            )
            / 2,
            (np.pi / 4, np.pi / 4, 1 / 2),
        ),
    ],
)
def test(mat, expected):
    assert np.all(np.isclose(bloch_sphere_rep(mat), expected))
