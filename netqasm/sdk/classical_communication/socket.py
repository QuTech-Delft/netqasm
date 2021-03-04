"""TODO write about classical communication"""
from __future__ import annotations

import abc
from typing import Optional
from typing import TYPE_CHECKING

from netqasm.sdk.classical_communication.message import StructuredMessage

if TYPE_CHECKING:
    from netqasm.sdk.config import LogConfig


class Socket(abc.ABC):
    def __init__(
        self,
        app_name: str,
        remote_app_name: str,
        socket_id: int = 0,
        timeout: Optional[float] = None,
        use_callbacks: bool = False,
        log_config: Optional[LogConfig] = None,
    ):
        """Socket used to communicate classical data between applications."""
        pass

    @abc.abstractmethod
    def send(self, msg: str) -> None:
        """Sends a message to the remote node."""
        pass

    @abc.abstractmethod
    def recv(self, block: bool = True, timeout: Optional[float] = None, maxsize: Optional[int] = None) -> str:
        """Receive a message from the remote node."""
        pass

    def send_structured(self, msg: StructuredMessage) -> None:
        """Sends a structured message (with header and payload) to the remote node."""
        raise NotImplementedError

    def recv_structured(
        self, block: bool = True, timeout: Optional[float] = None, maxsize: Optional[int] = None
    ) -> StructuredMessage:
        """Receive a message (with header and payload) from the remote node."""
        raise NotImplementedError

    def send_silent(self, msg: str) -> None:
        """Sends a message without logging"""
        raise NotImplementedError

    def recv_silent(self, block: bool = True, timeout: Optional[float] = None, maxsize: int = None) -> str:
        """Receive a message without logging"""
        raise NotImplementedError

    def recv_callback(self, msg: str) -> None:
        """This method gets called when a message is received.

        Subclass to define behaviour.

        NOTE: This only happens if `self.use_callbacks` is set to `True`.
        """
        pass

    def conn_lost_callback(self) -> None:
        """This method gets called when the connection is lost.

        Subclass to define behaviour.

        NOTE: This only happens if `self.use_callbacks` is set to `True`.
        """
        pass
