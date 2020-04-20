import pytest

from netqasm.sdk.futures import Future, NoValueError, NonConstantIndexError
from netqasm.parsing import parse_register
from netqasm.sdk.shared_memory import SharedMemory


class MockConnnection:
    def __init__(self):
        self._variables = {}
        self._shared_memory = SharedMemory()


def test_non_constant_index():
    conn = MockConnnection()

    m = Future(conn, address=0, index=parse_register("R0"))
    with pytest.raises(NonConstantIndexError):
        print(m)


def test_no_array():
    conn = MockConnnection()

    m = Future(conn, address=0, index=0)
    with pytest.raises(IndexError):
        print(m)


def test_no_value():
    conn = MockConnnection()
    conn._shared_memory.init_new_array(address=0, length=1)

    m = Future(conn, address=0, index=0)
    print(m)
    with pytest.raises(NoValueError):
        print(m * 2)


def test_with_value():
    conn = MockConnnection()
    conn._shared_memory.init_new_array(address=0, length=1)
    conn._shared_memory.set_array_part(address=0, index=0, value=4)

    m = Future(conn, address=0, index=0)
    print(m)
    print(m * 2)
    assert m * 2 == 8
