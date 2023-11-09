"""
External program interface.
"""

from abc import ABC, abstractmethod

from netqasm.sdk.run import Context

class Program(ABC):
    def __init__(self):
        print(__name__)

    @abstractmethod
    def run(self, context: Context):
        raise NotImplementedError
