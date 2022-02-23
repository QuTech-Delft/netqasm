from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .futures import BaseFuture


class SdkConstraint:
    """A constraint that can be used in exit conditions in SDK loops."""

    pass


class ValueAtMostConstraint(SdkConstraint):
    """A constraint that a certain variable should be at most another value."""

    def __init__(self, future: BaseFuture, value: int) -> None:
        """ValueAtMostConstraint constructor.

        :param future: the variable that should be at most the given value
        :param value: the maximum value that the given future may have
        """
        self._future = future
        self._value = value

    @property
    def future(self) -> BaseFuture:
        return self._future

    @property
    def value(self) -> int:
        return self._value
