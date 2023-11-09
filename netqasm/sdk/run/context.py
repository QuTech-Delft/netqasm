"""
External execution context interface.
"""

from abc import ABC, abstractmethod
from typing import Dict

from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.classical_communication.socket import Socket
from netqasm.sdk.epr_socket import EPRSocket

class Context(ABC):
    def __init__(self):
        pass

    @property
    @abstractmethod
    def connection(self) -> BaseNetQASMConnection:
        raise NotImplementedError

    @property
    @abstractmethod
    def csockets(self) -> Dict[str, Socket]:
        raise NotImplementedError

    @property
    @abstractmethod
    def epr_sockets(self) -> Dict[str, EPRSocket]:
        raise NotImplementedError
