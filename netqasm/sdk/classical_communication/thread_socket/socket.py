import os
from typing import Dict, Optional

from netqasm.logging import get_netqasm_logger
from ..socket import Socket
from .socket_hub import _socket_hub
from netqasm.log_util import LineTracker
from netqasm.output import SocketOperation, ClassCommLogger
from netqasm.sdk.config import LogConfig


def log_send(method):
    def new_method(self, msg):
        hln = None
        hfl = None
        if self._line_tracker is not None:
            hostline = self._line_tracker.get_line()
            if hostline is not None:
                hln = hostline.lineno
                hfl = hostline.filename

        if self._comm_logger is not None:
            log = f"Send classical message to {self.remote_node_name}: {msg}"
            self._comm_logger.log(
                socket_op=SocketOperation.SEND,
                msg=msg,
                sender=self._node_name,
                receiver=self._remote_node_name,
                socket_id=self._id,
                hln=hln,
                hfl=hfl,
                log=log,
            )

        method(self, msg)

    return new_method


def log_recv(method):
    def new_method(self, block=True, timeout=None):
        hln = None
        hfl = None
        if self._line_tracker is not None:
            hostline = self._line_tracker.get_line()
            if hostline is not None:
                hln = hostline.lineno
                hfl = hostline.filename

        if self._comm_logger is not None:
            log = f"Waiting for a classical message from {self.remote_node_name}..."
            self._comm_logger.log(
                socket_op=SocketOperation.WAIT_RECV,
                msg=None,
                sender=self._remote_node_name,
                receiver=self._node_name,
                socket_id=self._id,
                hln=hln,
                hfl=hfl,
                log=log,
            )

        msg = method(self, block, timeout)

        if self._comm_logger is not None:
            log = f"Message received from {self.remote_node_name}: {msg}"
            self._comm_logger.log(
                socket_op=SocketOperation.RECV,
                msg=msg,
                sender=self._remote_node_name,
                receiver=self._node_name,
                socket_id=self._id,
                hln=hln,
                hfl=hfl,
                log=log,
            )

        return msg

    return new_method


class ThreadSocket(Socket):

    _COMM_LOGGERS: Dict[str, Optional[ClassCommLogger]] = {}

    def __init__(self, node_name, remote_node_name, socket_id=0, timeout=None,
                 use_callbacks=False, log_config=None):
        """Socket used when applications run under the same process in different threads.

        This connection is only a hack used in simulations to easily develop applications and protocols.

        Parameters
        ----------
        node_name : int
            Node ID of the local node.
        remote_node_name : str
            Node ID of the remote node.
        socket_id : int, optional
            ID of the socket (can be seen as a port)
        timeout : float, optional
            Optionally use a timeout for trying to setup a connection with another node.
        use_callbacks : bool, optional
            Whether to use callbacks or not.
        comm_log_dir : str, optional
            Path to log classical communication to. File name will be "{node_name}_class_comm.log"
        """
        if node_name == remote_node_name:
            raise ValueError(f"Cannot connect to itself node_name {node_name} = remote_node_name {remote_node_name}")
        self._node_name = node_name
        self._remote_node_name = remote_node_name
        self._id = socket_id

        if log_config is None:
            log_config = LogConfig()

        self._line_tracker = LineTracker(log_config=log_config)
        self._track_lines = log_config.track_lines

        # Use callbacks
        self._use_callbacks = use_callbacks

        # Received messages
        self._received_messages = []

        # The global socket hub
        self._socket_hub = _socket_hub

        # Logger
        self._logger = get_netqasm_logger(f"{self.__class__.__name__}{self.key}")

        self._logger.debug("Setting up connection")

        # Classical communication logger
        if log_config.comm_log_dir is None:
            self._comm_logger = None
        else:
            self._comm_logger = self.__class__.get_comm_logger(
                node_name=self.node_name,
                comm_log_dir=log_config.comm_log_dir,
            )

        # Connect
        self._socket_hub.connect(self, timeout=timeout)

    @classmethod
    def get_comm_logger(cls, node_name, comm_log_dir):
        comm_logger = cls._COMM_LOGGERS.get(node_name)
        if comm_logger is None:
            filename = f"{str(node_name).lower()}_class_comm.yaml"
            filepath = os.path.join(comm_log_dir, filename)
            comm_logger = ClassCommLogger(filepath=filepath)
            cls._COMM_LOGGERS[node_name] = comm_logger
        return comm_logger

    def __del__(self):
        if self.connected:
            self._logger.debug("Closing connection")
        self._connected = False
        self._socket_hub.disconnect(self)

    @property
    def node_name(self):
        return self._node_name

    @property
    def remote_node_name(self):
        return self._remote_node_name

    @property
    def id(self):
        return self._id

    @property
    def key(self):
        return self.node_name, self.remote_node_name, self.id

    @property
    def remote_key(self):
        return self.remote_node_name, self.node_name, self.id

    @property
    def connected(self):
        return self._socket_hub.is_connected(self)

    @property
    def use_callbacks(self):
        return self._use_callbacks

    @use_callbacks.setter
    def use_callbacks(self, value):
        self._use_callbacks = value

    @log_send
    def send(self, msg):
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

        self._socket_hub.send(self, msg)

    @log_recv
    def recv(self, block=True, timeout=None):
        """Receive a message form the remote node.

        If block is True the method will block until there is a message or a timeout is reached.
        Otherwise the method will raise a `RuntimeError` if there is not message to receive directly.

        Parameters
        ----------
        block : bool
            Whether to block for an available message
        timeout : float, optional
            Optionally use a timeout for trying to recv a message. Only used if `block=True`.

        Returns
        -------
        str
            The message received

        Raises
        ------
        RuntimeError
            If `block=False` and there is no available message
        """
        return self._socket_hub.recv(self, block=block, timeout=timeout)

    def wait(self):
        """Waits until the connection gets lost"""
        while True:
            if not self.connected:
                return


class StorageThreadSocket(ThreadSocket):
    def __init__(self, node_name, remote_node_name, **kwargs):
        """ThreadSocket that simply stores any message comming in"""
        self._storage = []
        super().__init__(node_name, remote_node_name, use_callbacks=True, **kwargs)

    def recv_callback(self, msg):
        self._storage.append(msg)
