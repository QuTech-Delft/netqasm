import pytest
import logging
from concurrent.futures import ThreadPoolExecutor
from timeit import default_timer as timer

from netqasm.sdk import ThreadSocket
from netqasm.logging import set_log_level


def execute_functions(functions):
    """Executes functions in different threads"""
    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = []
        for function in functions:
            future = executor.submit(function)
            futures.append(future)

        for future in futures:
            future.result()


def test_init_error():
    with pytest.raises(ValueError):
        ThreadSocket(0, 0, track_lines=False)


def test_connection_error():
    with pytest.raises(TimeoutError):
        ThreadSocket("alice", "bob", timeout=1, track_lines=False)


def test_connect():

    def connect_alice():
        ThreadSocket("alice", "bob", timeout=1, track_lines=False)

    def connect_bob():
        socket = ThreadSocket("bob", "alice", timeout=1, track_lines=False)
        socket.wait()

    execute_functions([connect_alice, connect_bob])


def test_set_callback():

    def connect_alice():
        ThreadSocket("alice", "bob", timeout=1, track_lines=False)

    def connect_bob():
        socket = ThreadSocket("bob", "alice", timeout=1, track_lines=False)
        assert not socket.use_callbacks
        socket.use_callbacks = True
        assert socket.use_callbacks
        socket.wait()

    execute_functions([connect_alice, connect_bob])


def test_connection_lost():
    callbacks = [0]

    class CallbackSocket(ThreadSocket):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs, use_callbacks=True)

        def conn_lost_callback(self):
            callbacks[0] += 1

    def connect_alice():
        CallbackSocket("alice", "bob", timeout=1, track_lines=False)

    def connect_bob():
        socket = CallbackSocket("bob", "alice", timeout=1, track_lines=False)
        socket.wait()

    execute_functions([connect_alice, connect_bob])

    assert callbacks[0] == 1


@pytest.mark.parametrize("msg", [
    None,
    0,
    [1, 2],
])
def test_faulty_send_type(msg):

    def connect_alice():
        socket = ThreadSocket("alice", "bob", timeout=1, track_lines=False)
        with pytest.raises(TypeError):
            socket.send(msg)

    def connect_bob():
        socket = ThreadSocket("bob", "alice", timeout=1, track_lines=False)
        socket.wait()

    execute_functions([connect_alice, connect_bob])


def test_faulty_send_connection():

    def connect_alice():
        ThreadSocket("alice", "bob", timeout=1, track_lines=False)

    def connect_bob():
        socket = ThreadSocket("bob", "alice", timeout=1, track_lines=False)
        socket.wait()
        with pytest.raises(ConnectionError):
            socket.send("")

    execute_functions([connect_alice, connect_bob])


def test_send_recv():
    msg = "hello"

    def alice():
        socket = ThreadSocket("alice", "bob", track_lines=False)
        socket.send(msg)

    def bob():
        socket = ThreadSocket("bob", "alice", track_lines=False)
        msg_recv = socket.recv(timeout=1)
        assert msg_recv == msg

    execute_functions([alice, bob])


def test_recv_block():

    def alice():
        socket = ThreadSocket("alice", "bob", track_lines=False)
        socket.wait()

    def bob():
        socket = ThreadSocket("bob", "alice", track_lines=False)
        with pytest.raises(RuntimeError):
            socket.recv(block=False)
        timeout = 1
        t_start = timer()
        with pytest.raises(TimeoutError):
            socket.recv(timeout=timeout)
        t_end = timer()
        t_elapsed = t_end - t_start
        print(t_elapsed)
        assert abs(timeout - t_elapsed) < 0.2

    execute_functions([alice, bob])


def test_ping_pong_counter():
    max_value = 10

    def alice():
        socket = ThreadSocket("alice", "bob", track_lines=False)
        counter = 0
        counter_values = [counter]
        socket.send(str(counter))
        while counter < max_value:
            counter = int(socket.recv())
            counter += 1
            counter_values.append(counter)
            socket.send(str(counter))
        socket.wait()
        print(counter_values)
        assert counter_values == list(range(0, max_value + 2, 2))

    def bob():
        socket = ThreadSocket("bob", "alice", track_lines=False)
        counter = 0
        counter_values = []
        while counter < max_value:
            counter = int(socket.recv())
            counter += 1
            counter_values.append(counter)
            socket.send(str(counter))
        print(counter_values)
        assert counter_values == list(range(1, max_value + 2, 2))

    execute_functions([alice, bob])


def test_ping_pong_counter_callbacks():
    max_value = 10

    class PingPongSocket(ThreadSocket):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs, use_callbacks=True)
            self.counter_values = []

        def recv_callback(self, msg):
            counter = int(msg)
            if counter > max_value:
                return
            counter += 1
            self.counter_values.append(counter)
            self.send(str(counter))

    def alice():
        socket = PingPongSocket("alice", "bob", track_lines=False)
        socket.send("0")
        print(socket.counter_values)
        assert socket.counter_values == list(range(2, max_value + 2, 2))

    def bob():
        socket = PingPongSocket("bob", "alice", track_lines=False)
        socket.wait()
        print(socket.counter_values)
        assert socket.counter_values == list(range(1, max_value + 2, 2))

    execute_functions([alice, bob])


if __name__ == '__main__':
    set_log_level(logging.DEBUG)
    test_connect()
    test_connection_lost()
    test_send_recv()
    test_recv_block()
    test_ping_pong_counter()
    test_ping_pong_counter_callbacks()
