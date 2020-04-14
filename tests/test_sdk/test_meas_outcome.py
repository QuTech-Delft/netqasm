import pytest

from netqasm.sdk.meas_outcome import MeasurementOutcome, NoValueError


class MockConnnection:
    def __init__(self):
        self._variables = {}

    def read_variable(self, var_name):
        return self._variables.get(var_name)


def test_no_var_name():
    conn = MockConnnection()

    m = MeasurementOutcome(conn, var_name=None)
    with pytest.raises(NoValueError):
        print(m)


def test_no_value():
    conn = MockConnnection()

    m = MeasurementOutcome(conn, var_name='m')
    print(m)
    with pytest.raises(NoValueError):
        print(m * 2)


def test_with_value():
    conn = MockConnnection()
    conn._variables['m'] = 4

    m = MeasurementOutcome(conn, var_name='m')
    print(m)
    print(m * 2)
    assert m * 2 == 8
