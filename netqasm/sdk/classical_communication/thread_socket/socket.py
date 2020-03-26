import logging

from ..socket import Socket
from .socket_hub import _socket_hub


class ThreadSocket(Socket):
    def __init__(self, node_id, remote_node_id, socket_id=0, timeout=None,
                 recv_callback=None, conn_lost_callback=None):
        """Socket used when applications run under the same process in different threads.

        This connection is only a hack used in simulations to easily develop applications and protocols.

        Parameters
        ----------
        node_id : int
            Node ID of the local node.
        remote_node_id : int
            Node ID of the local node.
        socket_id : int, optional
            ID of the socket (can be seen as a port)
        timeout : float, optional
            Optionally use a timeout for trying to setup a connection with another node.
        recv_callback : function
            A callback function to be executed when a message is received.
        conn_lost_callback : function
            A callback function to be executed when the connection is lost.
        """
        if node_id == remote_node_id:
            raise ValueError(f"Cannot connect to itself node_id {node_id} = remote_node_id {remote_node_id}")
        self._node_id = node_id
        self._remote_node_id = remote_node_id
        self._id = socket_id

        # Callback functions
        self._recv_callback = recv_callback
        self._conn_lost_callback = conn_lost_callback

        # Received messages
        self._received_messages = []

        # The global socket hub
        self._socket_hub = _socket_hub

        # Logger
        self._logger = logging.getLogger(f"{self.__class__.__name__}{self.key}")

        self._logger.debug(f"Setting up connection")

        # Connect
        self._socket_hub.connect(self, timeout=timeout)

    def __del__(self):
        if self.connected:
            self._logger.debug(f"Closing connection")
            self._connected = False
            self._socket_hub.disconnect(self)

    @property
    def node_id(self):
        return self._node_id

    @property
    def remote_node_id(self):
        return self._remote_node_id

    @property
    def id(self):
        return self._id

    @property
    def key(self):
        return self.node_id, self.remote_node_id, self.id

    @property
    def remote_key(self):
        return self.remote_node_id, self.node_id, self.id

    @property
    def connected(self):
        return self._socket_hub.is_connected(self)

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
        pass

    def recv(self, block=True):
        """Receive a message form the remote node.

        If block is True the method will block until there is a message.
        Otherwise the method will raise a `RuntimeError` if there is not message to receive directly.

        Parameters
        ----------
        block : bool
            Whether to block for an available message

        Returns
        -------
        str
            The message received

        Raises
        ------
        RuntimeError
            If `block=False` and there is no available message
        """
        pass
