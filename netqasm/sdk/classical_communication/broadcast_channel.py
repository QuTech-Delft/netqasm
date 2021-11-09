"""Interface for classical broadcasting between Hosts.

This module contains the `BroadcastChannel` class which is a base for representing
classical broadcasting (sending classical messages to all other nodes in the network)
between Hosts.
"""
from __future__ import annotations

import abc
from timeit import default_timer as timer
from typing import TYPE_CHECKING, List, Optional, Tuple, Type

if TYPE_CHECKING:
    from . import socket as sck


class BroadcastChannel(abc.ABC):
    """Socket for sending messages to all nodes in the network (broadcasting).

    A BroadcastChannel can be used by Hosts to broadcast a message to all other nodes
    in the network. It is very similar to a Socket object, just without an explicit
    single remote node.

    A BroadcastChannel is a local object that each node (that wants to send and
    receive broadcast messages) must instantiate themselves.
    """

    def __init__(
        self,
        app_name: str,
        timeout: Optional[float] = None,
        use_callbacks: bool = False,
    ):
        """BroadcastChannel constructor.

        :param app_name: application/Host name of this channel's constructor
        :param timeout: maximum time to try and create this channel before aborting
        :param use_callbacks: whether to use the `recv_callback` and
            `conn_lost_callback` callback methods
        """
        pass

    @abc.abstractmethod
    def send(self, msg: str) -> None:
        """Broadcast a message to all remote nodes."""
        pass

    @abc.abstractmethod
    def recv(self, block: bool = True) -> Tuple[str, str]:
        """Receive a message that was broadcast and from whom."""
        pass

    def recv_callback(self, remote_app_name: str, msg: str) -> None:
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


class BroadcastChannelBySockets(BroadcastChannel):
    """Implementation of a BroadcastChannel using a Socket for each remote node.

    Technically this is a multicast channel since the receiving nodes must be
    explicitly listed. It simply uses one-to-one sockets for every remote node.
    """

    def __init__(self, app_name: str, remote_app_names: List[str], **kwargs):
        """BroadcastChannel constructor.

        :param app_name: application/Host name of self
        :param remote_app_names: list of receiving remote Hosts
        """
        self._sockets = {
            remote_app_name: self._socket_class(
                app_name=app_name, remote_app_name=remote_app_name, **kwargs
            )
            for remote_app_name in remote_app_names
        }

    @property
    @abc.abstractmethod
    def _socket_class(self) -> Type[sck.Socket]:
        pass

    def send(self, msg: str) -> None:
        """Broadcast a message to all remote nodes."""
        for socket in self._sockets.values():
            socket.send(msg=msg)

    def recv(
        self, block: bool = True, timeout: Optional[float] = None
    ) -> Tuple[str, str]:
        """Receive a message that was broadcast.

        Parameters
        ----------
        block : bool
            Whether to block for an available message
        timeout : float, optional
            Optionally use a timeout for trying to recv a message. Only used if `block=True`.

        Returns
        -------
        tuple
            (remote_node_name, msg)

        Raises
        ------
        RuntimeError
            If `block=False` and there is no available message
        """
        t_start = timer()
        while block:
            for remote_node_name, socket in self._sockets.items():
                try:
                    msg = socket.recv(block=False)
                except RuntimeError:
                    continue
                else:
                    return remote_node_name, msg
            if block and timeout is not None:
                t_now = timer()
                t_elapsed = t_now - t_start
                if t_elapsed > timeout:
                    raise TimeoutError(
                        "Timeout while trying to receive broadcasted message"
                    )
        raise RuntimeError("No message broadcasted")
