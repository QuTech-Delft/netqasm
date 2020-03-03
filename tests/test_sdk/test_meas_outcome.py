import pytest

from netqasm.sdk.meas_outcome import MeasurementOutcome, NoValueError


def test_measurement_outcome():
    m = MeasurementOutcome(None, address=0)
    print(m)
    with pytest.raises(NoValueError):
        print(m * 2)
    m._value = 4
    print(m)
    print(m * 2)
    assert m * 2 == 8
