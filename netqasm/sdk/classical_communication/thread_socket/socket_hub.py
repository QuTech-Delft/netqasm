import logging
from time import sleep
from threading import Lock
from timeit import default_timer as timer


class _SocketHub:

    _CONNECT_SLEEP_TIME = 0.1

    def __init__(self):
        """Used to connect all sockets (:class:`~.ThreadSocket`) used between threads"""
        self._open_sockets = set()
        self._messages = {}
        self._recv_callbacks = {}
        self._conn_lost_callbacks = {}

        self._lock = Lock()

        self._logger = logging.getLogger(self.__class__.__name__)

    def connect(self, socket, timeout=None):
        """Connects a socket to another"""
        self._open_sockets.add(socket.key)
        self._add_callbacks(socket)

        self._wait_for_remote(socket, timeout=timeout)

    def is_connected(self, socket):
        return socket.key in self._open_sockets

    def _add_callbacks(self, socket):
        self._recv_callbacks[socket.key] = socket._recv_callback
        self._conn_lost_callbacks[socket.key] = socket._conn_lost_callback

    def disconnect(self, socket):
        with self._lock:
            conn_lost_callback = self._conn_lost_callbacks[socket.remote_key]
            if conn_lost_callback is not None:
                conn_lost_callback()
            for key in [socket.key, socket.remote_key]:
                self._open_sockets.remove(key)
                self._recv_callbacks.pop(key)
                self._conn_lost_callbacks.pop(key)

    def _wait_for_remote(self, socket, timeout=None):
        t_start = timer()
        while True:
            if socket.remote_key in self._open_sockets:
                self._logger.debug(f"Connection for socket {socket.key} successful")
                return
            t_now = timer()
            t_elapsed = t_now - t_start
            if timeout is not None:
                if t_elapsed > timeout:
                    node_id = socket.node_id
                    remote_node_id = socket.remote_node_id
                    socket_id = socket.id
                    raise ConnectionError(f"Timeout while connection node ID {node_id} to "
                                          f"{remote_node_id} using socket {socket_id}")
            self._logger.debug(f"Connection for socket {socket.key} failed, "
                               f"trying again in {self._CONNECT_SLEEP_TIME} s...")
            sleep(self._CONNECT_SLEEP_TIME)

    def send(self, socket, msg):
        pass


_socket_hub = _SocketHub()
