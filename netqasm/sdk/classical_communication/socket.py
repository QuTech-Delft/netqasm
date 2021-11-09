"""Interface for classical communication between Hosts.

This module contains the `Socket` class which is a base for representing classical
communication (sending and receiving classical messages) between Hosts.
"""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Optional

from netqasm.sdk.classical_communication.message import StructuredMessage

if TYPE_CHECKING:
    from netqasm.sdk import config


class Socket(abc.ABC):
    """Base class for classical sockets.

    Classical communication is modelled by sockets, which are also widely used
    in purely classical applications involving communication.

    If a node wants to communicate arbitrary classical messages with another node, this
    communication must be done between the Hosts of these nodes. Both Hosts should
    instantiate a Socket object with the other Host as 'remote'. Upon creation, the
    Socket objects try to connect to each other. Only after this has succeeded, the
    sockets can be used.

    The main methods of a Socket are `send` and `recv`, which are used to send a
    message to the remote Host, and wait to receive a message from the other Host,
    respectively. Messages are str (string) objects. To send a number, convert it
    to a string before sending, and convert it back after receiving.

    There are some variations on the `send` and `recv` methods which may be useful
    in specific scenarios. See their own documentation for their use.

    NOTE: At the moment, Sockets are not part of the compilation process yet. Therefore,
    they don't need to be part of a Connection, and operations on Sockets do not need
    to be flushed before they are executed (they are executed immediately).
    This also means that e.g. a `recv` operation, which is blocking by default,
    acutally blocks the whole application script. **So, if any quantum operations
    should be executed before such a `recv` statement, make sure that these operations
    are flushed before blocking on `recv`**.

    Implementations (subclasses) of Sockets may be quite different, depending on the
    runtime environment. A physical setup (with real hardware) may implement this as
    TCP sockets. A simulator might use inter-thread communication (see e.g.
    `ThreadSocket`), or another custom object type.
    """

    def __init__(
        self,
        app_name: str,
        remote_app_name: str,
        socket_id: int = 0,
        timeout: Optional[float] = None,
        use_callbacks: bool = False,
        log_config: Optional[config.LogConfig] = None,
    ):
        """Socket constructor.

        :param app_name: application/Host name of this socket's owner
        :param remote_app_name: application/Host name of this socket's remote
        :param socket_id: local ID to use for this socket
        :param timeout: maximum amount of real time to try to connect to the remote
            socket
        :param use_callbacks: whether to call the `recv_callback` method upon receiving
            a message
        :param log_config: logging configuration for this socket
        """
        pass

    @abc.abstractmethod
    def send(self, msg: str) -> None:
        """Send a message to the remote node."""
        pass

    @abc.abstractmethod
    def recv(
        self,
        block: bool = True,
        timeout: Optional[float] = None,
        maxsize: Optional[int] = None,
    ) -> str:
        """Receive a message from the remote node."""
        pass

    def send_structured(self, msg: StructuredMessage) -> None:
        """Sends a structured message (with header and payload) to the remote node."""
        raise NotImplementedError

    def recv_structured(
        self,
        block: bool = True,
        timeout: Optional[float] = None,
        maxsize: Optional[int] = None,
    ) -> StructuredMessage:
        """Receive a message (with header and payload) from the remote node."""
        raise NotImplementedError

    def send_silent(self, msg: str) -> None:
        """Sends a message without logging"""
        raise NotImplementedError

    def recv_silent(
        self, block: bool = True, timeout: Optional[float] = None, maxsize: int = None
    ) -> str:
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
