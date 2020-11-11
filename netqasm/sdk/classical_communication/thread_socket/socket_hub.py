from time import sleep
from threading import Lock
from collections import defaultdict
from timeit import default_timer as timer
from weakref import WeakMethod

from netqasm.logging.glob import get_netqasm_logger


class _SocketHub:

    _CONNECT_SLEEP_TIME = 0.1
    _RECV_SLEEP_TIME = 0.1

    def __init__(self):
        """Used to connect all sockets (:class:`~.ThreadSocket`) used between threads"""
        # NOTE a socket gets tracked at two places, the _open_sockets and _remote_sockets
        # the idea is that when a connection is closed it removes itself from the _open_sockets
        # but it is the task of the other end to remote it from the _remote_sockets.
        # This is to prevent a connection from opening and closing on one side before
        # the sides notices and waits for ever.
        self._open_sockets = set()
        self._remote_sockets = set()

        self._messages = defaultdict(list)
        self._recv_callbacks = {}
        self._conn_lost_callbacks = {}

        self._lock = Lock()

        self._logger = get_netqasm_logger(self.__class__.__name__)

    def connect(self, socket, timeout=None):
        """Connects a socket to another"""
        self._open_sockets.add(socket.key)
        self._remote_sockets.add(socket.key)
        self._add_callbacks(socket)

        self._wait_for_remote(socket, timeout=timeout)

    def _add_callbacks(self, socket):
        if socket.use_callbacks:
            self._recv_callbacks[socket.key] = WeakMethod(socket.recv_callback)
            self._conn_lost_callbacks[socket.key] = WeakMethod(socket.conn_lost_callback)

    def is_connected(self, socket):
        return all(key in self._open_sockets for key in [socket.key, socket.remote_key])

    def disconnect(self, socket):
        """Disconnect a socket"""
        with self._lock:
            conn_lost_callback = self._conn_lost_callbacks.get(socket.remote_key)
            if conn_lost_callback is not None:
                method = conn_lost_callback()
                # This is a WeakMethod so check if it exists
                if method is None:
                    self._logger.warning(f"Trying to call lost connection callback "
                                         f"for socket {socket.remote_key} but object is garbage collected")
                else:
                    method()

            if socket.key in self._open_sockets:
                self._open_sockets.remove(socket.key)
            if socket.remote_key in self._remote_sockets:
                self._remote_sockets.remove(socket.remote_key)
            self._recv_callbacks.pop(socket.key, None)
            self._conn_lost_callbacks.pop(socket.key, None)

    def _wait_for_remote(self, socket, timeout=None):
        """Wait for a remote socket to become active"""
        t_start = timer()
        while True:
            if socket.remote_key in self._open_sockets:
                self._logger.debug(f"Connection for socket {socket.key} successful")
                return
            if socket.remote_key in self._remote_sockets:
                self._logger.debug(f"Connection for socket {socket.key} was successful but closed again")
                return
            t_now = timer()
            t_elapsed = t_now - t_start
            if timeout is not None:
                if t_elapsed > timeout:
                    app_name = socket.app_name
                    remote_app_name = socket.remote_app_name
                    socket_id = socket.id
                    raise TimeoutError(f"Timeout while connection node ID {app_name} to "
                                       f"{remote_app_name} using socket {socket_id}")
            self._logger.debug(f"Connection for socket {socket.key} failed, "
                               f"trying again in {self._CONNECT_SLEEP_TIME} s...")
            sleep(self.__class__._CONNECT_SLEEP_TIME)

    def send(self, socket, msg):
        """Send a message using a given socket"""
        recv_callback = self._recv_callbacks.get(socket.remote_key)
        if recv_callback is not None:
            self._logger.debug(f"Message {msg} sent on socket {socket.key}, calling callback for recv")
            method = recv_callback()
            # This is a WeakMethod so check if it exists
            if method is None:
                self._logger.warning(f"Trying to call recv callback "
                                     f"for socket {socket.remote_key} but object is garbage collected")
            else:
                method(msg)
        else:
            self._logger.debug(f"Message {msg} sent on socket {socket.key}, adding to pending received messages")
            with self._lock:
                self._messages[socket.remote_key].append(msg)

    def recv(self, socket, block=True, timeout=None):
        """Recv a message to a given socket"""
        t_start = timer()
        while True:
            with self._lock:
                messages = self._messages[socket.key]
            if len(messages) == 0:
                if not block:
                    raise RuntimeError(f"No message to receive on socket {socket.key}")
            else:
                with self._lock:
                    msg = messages.pop(0)
                self._logger.debug(f"Got message {msg} for socket {socket.key}")
                return msg
            if timeout is not None:
                t_now = timer()
                t_elapsed = t_now - t_start
                if t_elapsed > timeout:
                    raise TimeoutError(f"Timeout while trying to receive message for socket {socket.key}")
            self._logger.debug(f"No message yet for socket {socket.key}, "
                               f"trying again in {self._RECV_SLEEP_TIME} s...")
            sleep(self.__class__._RECV_SLEEP_TIME)


_socket_hub = _SocketHub()


def reset_socket_hub():
    _socket_hub.__init__()
