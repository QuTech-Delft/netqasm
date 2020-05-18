from enum import Enum

from netqasm.logging import get_netqasm_logger, setup_file_logger
from netqasm.logging import _COMM_LOGGER_FIELDS, _CommLogHeaders, setup_comm_logger_formatter
from ..socket import Socket
from .socket_hub import _socket_hub
from netqasm.log_util import LineTracker


class SocketOperation(Enum):
    SEND = "SEND"
    RECV = "RECV"
    WAIT_RECV = "WAIT_RECV"


def log_send(method):
    def new_method(self, msg):
        if self._comm_logger is not None:
            self._comm_logger.info(
                f"Send classical message to {self.remote_node_name}: {msg}",
                extra=self.get_extra_log_fields(SocketOperation.SEND))

        method(self, msg)

    return new_method


def log_recv(method):
    def new_method(self, block=True, timeout=None):
        if self._comm_logger is not None:
            self._comm_logger.info(
                f"Waiting for a classical message from {self.remote_node_name}...",
                extra=self.get_extra_log_fields(SocketOperation.WAIT_RECV))

        msg = method(self, block, timeout)

        if self._comm_logger is not None:
            self._comm_logger.info(
                f"Message received from {self.remote_node_name}: {msg}",
                extra=self.get_extra_log_fields(SocketOperation.RECV))

        return msg

    return new_method


class ThreadSocket(Socket):
    def __init__(self, node_name, remote_node_name, socket_id=0, timeout=None,
                 use_callbacks=False, comm_log_dir=None, track_lines=True):
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

        self._line_tracker = LineTracker(level=2, track_lines=track_lines)
        self._track_lines = track_lines

        # Use callbacks
        self._use_callbacks = use_callbacks

        # Received messages
        self._received_messages = []

        # The global socket hub
        self._socket_hub = _socket_hub

        # Logger
        self._logger = get_netqasm_logger(f"{self.__class__.__name__}{self.key}")

        self._logger.debug(f"Setting up connection")

        # Classical communication logger
        self._comm_logger = setup_file_logger(
            cls=self.__class__,
            name=self.node_name,
            log_dir=comm_log_dir,
            filename=f"{str(self.node_name).lower()}_class_comm.log",
            formatter=setup_comm_logger_formatter())

        # Connect
        self._socket_hub.connect(self, timeout=timeout)

    def __del__(self):
        if self.connected:
            self._logger.debug(f"Closing connection")
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

    def get_extra_log_fields(self, operation):
        """Returns the `extra` field to pass to the logger.

        operation : SocketOperation
        """
        lineno = self._line_tracker.get_line()
        hln = _COMM_LOGGER_FIELDS[_CommLogHeaders.HLN]
        op = _COMM_LOGGER_FIELDS[_CommLogHeaders.OP]
        return {
            hln: lineno,
            op: operation
        }

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

    def wait(self):
        """Waits until the connection gets lost"""
        while True:
            if not self.connected:
                return
