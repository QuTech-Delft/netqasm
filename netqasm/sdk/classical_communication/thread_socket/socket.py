"""Classical socket implementation using a hub that is shared across threads.

This module contains the ThreadSocket class which is an implementation of the Socket
interface that can be used by Hosts that run in a multi-thread simulation.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from netqasm.logging.glob import get_netqasm_logger
from netqasm.logging.output import ClassCommLogger, SocketOperation
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.config import LogConfig
from netqasm.util.log import LineTracker

from ..socket import Socket
from .socket_hub import _socket_hub, _SocketHub

if TYPE_CHECKING:
    import logging

T_ThreadSocketKey = Tuple[str, str, int]


def trim_msg(msg: str) -> str:
    trimmed_msg = msg
    if trimmed_msg.endswith("EOF"):
        trimmed_msg = trimmed_msg.split("EOF")[0]
    return trimmed_msg


def log_send(method):
    def new_method(self, msg: str) -> None:
        hln = None
        hfl = None
        if self._line_tracker is not None:
            hostline = self._line_tracker.get_line()
            if hostline is not None:
                hln = hostline.lineno
                hfl = hostline.filename

        if self._comm_logger is not None:
            trimmed_msg = trim_msg(msg)
            log = f"Send classical message to {self.remote_app_name}: {trimmed_msg}"
            self._comm_logger.log(
                socket_op=SocketOperation.SEND,
                msg=trimmed_msg,
                sender=self._app_name,
                receiver=self._remote_app_name,
                socket_id=self._id,
                hln=hln,
                hfl=hfl,
                log=log,
            )

        method(self, msg)

    return new_method


def log_send_structured(method):
    def new_method(self, msg: StructuredMessage):
        hln = None
        hfl = None
        if self._line_tracker is not None:
            hostline = self._line_tracker.get_line()
            if hostline is not None:
                hln = hostline.lineno
                hfl = hostline.filename

        logged_msg = f"{msg.header}: {msg.payload}"
        raw_msg = json.dumps(msg.__dict__)

        if self._comm_logger is not None:
            log = f"Send classical message to {self.remote_app_name}: {raw_msg}"
            self._comm_logger.log(
                socket_op=SocketOperation.SEND,
                msg=logged_msg,
                sender=self._app_name,
                receiver=self._remote_app_name,
                socket_id=self._id,
                hln=hln,
                hfl=hfl,
                log=log,
            )

        method(self, raw_msg)

    return new_method


def log_recv(method):
    def new_method(self, *args, **kwargs):
        hln = None
        hfl = None
        if self._line_tracker is not None:
            hostline = self._line_tracker.get_line()
            if hostline is not None:
                hln = hostline.lineno
                hfl = hostline.filename

        if self._comm_logger is not None:
            log = f"Waiting for a classical message from {self.remote_app_name}..."
            self._comm_logger.log(
                socket_op=SocketOperation.WAIT_RECV,
                msg=None,
                sender=self._remote_app_name,
                receiver=self._app_name,
                socket_id=self._id,
                hln=hln,
                hfl=hfl,
                log=log,
            )

        msg = method(self, *args, **kwargs)

        if self._comm_logger is not None:
            trimmed_msg = trim_msg(msg)
            log = f"Message received from {self.remote_app_name}: {trimmed_msg}"
            self._comm_logger.log(
                socket_op=SocketOperation.RECV,
                msg=trimmed_msg,
                sender=self._remote_app_name,
                receiver=self._app_name,
                socket_id=self._id,
                hln=hln,
                hfl=hfl,
                log=log,
            )

        return msg

    return new_method


def log_recv_structured(method):
    def new_method(self, *args, **kwargs):
        hln = None
        hfl = None
        if self._line_tracker is not None:
            hostline = self._line_tracker.get_line()
            if hostline is not None:
                hln = hostline.lineno
                hfl = hostline.filename

        if self._comm_logger is not None:
            log = f"Waiting for a classical message from {self.remote_app_name}..."
            self._comm_logger.log(
                socket_op=SocketOperation.WAIT_RECV,
                msg=None,
                sender=self._remote_app_name,
                receiver=self._app_name,
                socket_id=self._id,
                hln=hln,
                hfl=hfl,
                log=log,
            )

        raw_msg = method(self, *args, **kwargs)
        msg_dict = json.loads(raw_msg)
        msg = StructuredMessage(header=msg_dict["header"], payload=msg_dict["payload"])
        logged_msg = f"{msg.header}: {msg.payload}"

        if self._comm_logger is not None:
            log = f"Message received from {self.remote_app_name}: {msg}"
            self._comm_logger.log(
                socket_op=SocketOperation.RECV,
                msg=logged_msg,
                sender=self._remote_app_name,
                receiver=self._app_name,
                socket_id=self._id,
                hln=hln,
                hfl=hfl,
                log=log,
            )

        return msg

    return new_method


class ThreadSocket(Socket):
    """Classical socket implementation for multi-threaded simulations.

    This implementation should be used when the simulation consists of a single process,
    with a thread for each Host. A global SocketHub instance must be available and
    shared between all threads. The ThreadSocket instance for a Host can then 'send'
    and 'receive' messages to/from other Hosts by writing/reading from the shared
    SocketHub memory.

    Currently only used with the SquidASM simulator backend.
    """

    _COMM_LOGGERS: Dict[str, Optional[ClassCommLogger]] = {}
    _SOCKET_HUB: _SocketHub = _socket_hub

    def __init__(
        self,
        app_name: str,
        remote_app_name: str,
        socket_id: int = 0,
        timeout: Optional[float] = None,
        use_callbacks: bool = False,
        log_config: Optional[LogConfig] = None,
    ):
        """ThreadSocket constructor.

        :param app_name: application/Host name of this socket's owner
        :param remote_app_name: remote application/Host name
        :param socket_id: local ID to use for this socket
        :param timeout: maximum amount of real time to try to connect to the remote
            socket
        :param use_callbacks: whether to call the `recv_callback` method upon receiving
            a message
        :param log_config: logging configuration for this socket
        """
        self._app_name: str = app_name
        self._remote_app_name: str = remote_app_name
        self._id: int = socket_id
        if app_name == remote_app_name:
            raise ValueError(
                f"Cannot connect to itself app_name {app_name} = remote_app_name {remote_app_name}"
            )

        if log_config is None:
            log_config = LogConfig()

        self._line_tracker: LineTracker = LineTracker(log_config=log_config)
        self._track_lines: bool = log_config.track_lines

        # Use callbacks
        self._use_callbacks: bool = use_callbacks

        # Received messages
        # TODO: remove?
        self._received_messages: List[str] = []

        # Logger
        self._logger: logging.Logger = get_netqasm_logger(
            f"{self.__class__.__name__}{self.key}"
        )

        self._logger.debug("Setting up connection")

        # Classical communication logger
        self._comm_logger: Optional[ClassCommLogger]
        if log_config.comm_log_dir is None:
            self._comm_logger = None
        else:
            self._comm_logger = self.__class__.get_comm_logger(
                app_name=self.app_name,
                comm_log_dir=log_config.comm_log_dir,
            )

        # Connect
        self._SOCKET_HUB.connect(self, timeout=timeout)

    @classmethod
    def get_comm_logger(cls, app_name: str, comm_log_dir: str) -> ClassCommLogger:
        comm_logger = cls._COMM_LOGGERS.get(app_name)
        if comm_logger is None:
            filename = f"{str(app_name).lower()}_class_comm.yaml"
            filepath = os.path.join(comm_log_dir, filename)
            comm_logger = ClassCommLogger(filepath=filepath)
            cls._COMM_LOGGERS[app_name] = comm_logger
        return comm_logger

    def __del__(self) -> None:
        if self.connected:
            self._logger.debug("Closing connection")
        self._connected = False
        self._SOCKET_HUB.disconnect(self)

    @property
    def app_name(self) -> str:
        return self._app_name

    @property
    def remote_app_name(self) -> str:
        return self._remote_app_name

    @property
    def id(self) -> int:
        return self._id

    @property
    def key(self) -> T_ThreadSocketKey:
        return self.app_name, self.remote_app_name, self.id

    @property
    def remote_key(self) -> T_ThreadSocketKey:
        return self.remote_app_name, self.app_name, self.id

    @property
    def connected(self) -> bool:
        return self._SOCKET_HUB.is_connected(self)

    @property
    def use_callbacks(self) -> bool:
        return self._use_callbacks

    @use_callbacks.setter
    def use_callbacks(self, value: bool) -> None:
        self._use_callbacks = value

    @log_send
    def send(self, msg: str) -> None:
        """Sends a message to the remote node.

        Parameters
        ----------
        msg : str
            Message to be sent.

        Raises
        ------
        ConnectionError
            If the remote connection is unresponsive.
        """
        if not isinstance(msg, str):
            raise TypeError(f"Messages needs to be a string, not {type(msg)}")
        if not self.connected:
            raise ConnectionError("Socket is not connected so cannot send")

        self._SOCKET_HUB.send(self, msg)

    @log_recv
    def recv(
        self,
        block: bool = True,
        timeout: Optional[float] = None,
        maxsize: Optional[int] = None,
    ) -> str:
        """Receive a message form the remote node.

        If block is True the method will block until there is a message or a timeout is reached.
        Otherwise the method will raise a `RuntimeError` if there is not message to receive directly.

        Parameters
        ----------
        block : bool
            Whether to block for an available message
        timeout : float, optional
            Optionally use a timeout for trying to recv a message. Only used if `block=True`.
        maxsize : int
            How many bytes to maximally receive (not used here)

        Returns
        -------
        str
            The message received

        Raises
        ------
        RuntimeError
            If `block=False` and there is no available message
        """
        # TODO use maxsize?
        msg = self._SOCKET_HUB.recv(self, block=block, timeout=timeout)
        if not isinstance(msg, str):
            raise RuntimeError(f"Received message of type {type(msg)} instead of str")
        return msg

    @log_send_structured
    def send_structured(self, msg: StructuredMessage) -> None:
        if not self.connected:
            raise ConnectionError("Socket is not connected so cannot send")

        self._SOCKET_HUB.send(self, msg)

    @log_recv_structured
    def recv_structured(
        self,
        block: bool = True,
        timeout: Optional[float] = None,
        maxsize: Optional[int] = None,
    ) -> StructuredMessage:
        # TODO use maxsize?
        msg = self._SOCKET_HUB.recv(self, block=block, timeout=timeout)
        # if not isinstance(msg, StructuredMessage):
        #     raise RuntimeError(f"Received message of type {type(msg)} instead of StructuredMessage")
        # TODO fix return value type hints
        return msg  # type: ignore

    def wait(self) -> None:
        """Waits until the connection gets lost"""
        while True:
            if not self.connected:
                return

    def send_silent(self, msg: str) -> None:
        """Sends a message without logging"""
        if not isinstance(msg, str):
            raise TypeError(f"Messages needs to be a string, not {type(msg)}")
        if not self.connected:
            raise ConnectionError("Socket is not connected so cannot send")

        self._SOCKET_HUB.send(self, msg)

    def recv_silent(
        self, block: bool = True, timeout: Optional[float] = None, maxsize: int = None
    ) -> str:
        """Receive a message without logging"""
        msg = self._SOCKET_HUB.recv(self, block=block, timeout=timeout)
        if not isinstance(msg, str):
            raise RuntimeError(f"Received message of type {type(msg)} instead of str")
        return msg


class StorageThreadSocket(ThreadSocket):
    def __init__(self, app_name: str, remote_app_name: str, **kwargs):
        """ThreadSocket that simply stores any message comming in"""
        self._storage: List[str] = []
        super().__init__(app_name, remote_app_name, use_callbacks=True, **kwargs)

    def recv_callback(self, msg: str) -> None:
        self._storage.append(msg)
