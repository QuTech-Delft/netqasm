"""
External program interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from netqasm.sdk.run import Context


class Program(ABC):
    def __init__(self):
        print(__name__)

    @property
    def parameters(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def run(self, context: Context):
        raise NotImplementedError
