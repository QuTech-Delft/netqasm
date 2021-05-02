from typing import Union

from netqasm.sdk.futures import Array, Future, RegFuture
from netqasm.sdk.qubit import Qubit

T_Value = Union[Qubit, Future, RegFuture, Array]

__all__ = [
    # Classes
    "Future",
    "RegFuture",
    "Array",
    "Qubit",
    # Types
    "T_Value",
]
