from timeit import default_timer as timer

from ..socket import BroadcastChannel
from .socket import StorageThreadSocket


class ThreadBroadcastChannel(BroadcastChannel):
    def __init__(self, node_name, remote_node_names, **kwargs):
        """Socket used to broadcast classical data between applications.

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
        self._sockets = {remote_node_name: StorageThreadSocket(
            node_name=node_name,
            remote_node_name=remote_node_name,
            **kwargs)
            for remote_node_name in remote_node_names
        }

    def send(self, msg):
        """Broadcast a message to all remote node."""
        for socket in self._sockets.values():
            socket.send(msg=msg)

    def recv(self, block=True, timeout=None):
        """Receive a message that was broadcast.

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
        t_start = timer()
        while block:
            for remote_node_name, socket in self._sockets.items():
                if len(socket._storage) > 0:
                    return remote_node_name, socket._storage.pop(0)
            if block and timeout is not None:
                t_now = timer()
                t_elapsed = t_now - t_start
                if t_elapsed > timeout:
                    raise TimeoutError(f"Timeout while trying to receive broadcasted message")
        raise RuntimeError("No message broadcasted")
