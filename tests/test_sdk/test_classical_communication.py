import pytest
from time import sleep
from concurrent.futures import ThreadPoolExecutor

from netqasm.sdk import ThreadSocket


def test_init_error():
    with pytest.raises(ValueError):
        ThreadSocket(0, 0)


def test_connection_error():
    alice_id = 0
    bob_id = 1
    with pytest.raises(ConnectionError):
        ThreadSocket(alice_id, bob_id, timeout=1)


def test_connect():
    alice_id = 0
    bob_id = 1

    def connect_alice():
        socket = ThreadSocket(alice_id, bob_id, timeout=1)
        sleep(0.2)
        print(socket)

    def connect_bob():
        socket = ThreadSocket(bob_id, alice_id, timeout=1)
        sleep(0.2)
        print(socket)

    execute_functions([connect_alice, connect_bob])


def test_connection_lost():
    alice_id = 0
    bob_id = 1
    callbacks = [0]

    def callback():
        callbacks[0] += 1

    def connect_alice():
        socket = ThreadSocket(alice_id, bob_id, timeout=1, conn_lost_callback=callback)
        sleep(0.2)
        print(socket)

    def connect_bob():
        socket = ThreadSocket(bob_id, alice_id, timeout=1, conn_lost_callback=callback)
        sleep(1)
        print(socket)

    execute_functions([connect_alice, connect_bob])

    assert callbacks[0] == 1


def test_send_recv():
    alice_id = 0
    bob_id = 1
    msg = "hello"

    def alice():
        socket = ThreadSocket(alice_id, bob_id)
        socket.send(msg)

    def bob():
        socket = ThreadSocket(bob_id, alice_id)
        msg_recv = socket.recv()
        assert msg_recv == msg

    execute_functions([alice, bob])


def execute_functions(functions):
    """Executes functions in different threads"""
    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = []
        for function in functions:
            future = executor.submit(function)
            futures.append(future)

        for future in futures:
            future.result()


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    # test_connect()
    # test_connection_lost()
    test_send_recv()
