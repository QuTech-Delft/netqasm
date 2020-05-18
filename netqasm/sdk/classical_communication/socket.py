import abc


class Socket(abc.ABC):
    def __init__(self, node_name, remote_node_name, socket_id=0, timeout=None,
                 recv_callback=None, conn_lost_callback=None):
        """Socket used to communicate classical data between applications."""
        pass

    @abc.abstractmethod
    def send(self, msg):
        """Sends a message to the remote node."""
        pass

    @abc.abstractmethod
    def recv(self, block=True):
        """Receive a message form the remote node."""
        pass
