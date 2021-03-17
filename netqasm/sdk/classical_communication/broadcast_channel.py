import abc
from timeit import default_timer as timer


class BroadcastChannel(abc.ABC):
    def __init__(self, app_name, remote_app_names, timeout=None,
                 use_callbacks=False):
        """Socket used to broadcast classical data between applications."""
        pass

    @abc.abstractmethod
    def send(self, msg):
        """Broadcast a message to all remote node."""
        pass

    @abc.abstractmethod
    def recv(self, block=True):
        """Receive a message that was broadcast and from whom."""
        pass

    def recv_callback(self, remote_app_name, msg):
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


class BroadcastChannelBySockets(BroadcastChannel):
    def __init__(self, app_name, remote_app_names, **kwargs):
        """Socket used to broadcast classical data between applications.

        Simple uses one-to-one sockets to acheive a broadcast.
        These class of these sockets are defined by the class attribute `_socket_class`,
        which should be specified in a subclass.

        Parameters
        ----------
        app_name : int
            app name of the local node.
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
        self._sockets = {remote_app_name: self._socket_class(
            app_name=app_name,
            remote_app_name=remote_app_name,
            **kwargs)
            for remote_app_name in remote_app_names
        }

    @property
    @abc.abstractmethod
    def _socket_class(self):
        pass

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
                    raise TimeoutError("Timeout while trying to receive broadcasted message")
        raise RuntimeError("No message broadcasted")
