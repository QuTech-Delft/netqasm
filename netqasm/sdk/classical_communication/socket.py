import abc


class Socket(abc.ABC):
    def __init__(
        self,
        node_name,
        remote_node_name,
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
    def recv(self, block=True):
        """Receive a message from the remote node."""
        pass

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
