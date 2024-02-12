"""
External execution context interface.
"""

from abc import ABC, abstractmethod

from netqasm.sdk.connection import BaseNetQASMConnection

class Context(ABC):
    def __init__(self):
        pass

    @property
    @abstractmethod
    def connection(self) -> BaseNetQASMConnection:
        raise NotImplementedError
