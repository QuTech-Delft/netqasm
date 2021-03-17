"""TODO write about classical communication"""

import abc

from netqasm.sdk.classical_communication.message import StructuredMessage


class Socket(abc.ABC):
    def __init__(
        self,
        app_name,
        remote_app_name,
        socket_id=0,
        timeout=None,
        use_callbacks=False,
        log_config=None,
    ):
        """Socket used to communicate classical data between applications."""
        pass

    @abc.abstractmethod
    def send(self, msg):
        """Sends a message to the remote node."""
        pass

    @abc.abstractmethod
    def recv(self, block=True, maxsize=None):
        """Receive a message from the remote node."""
        pass

    def send_structured(self, msg: StructuredMessage) -> None:
        """Sends a structured message (with header and payload) to the remote node."""
        raise NotImplementedError

    def recv_structured(self, block=True, maxsize=None) -> StructuredMessage:
        """Receive a message (with header and payload) from the remote node."""
        raise NotImplementedError

    def send_silent(self, msg) -> None:
        """Sends a message without logging"""
        raise NotImplementedError

    def recv_silent(self, block=True, maxsize=None):
        """Receive a message without logging"""
        raise NotImplementedError

    def recv_callback(self, msg):
        """This method gets called when a message is received.

        Subclass to define behaviour.

        NOTE: This only happens if `self.use_callbacks` is set to `True`.
        """
        pass

    def conn_lost_callback(self):
        """This method gets called when the connection is lost.

        Subclass to define behaviour.

        NOTE: This only happens if `self.use_callbacks` is set to `True`.
        """
        pass
