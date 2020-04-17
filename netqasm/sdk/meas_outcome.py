# class NoValueError(RuntimeError):
#     pass


# class NonConstantIndexError(RuntimeError):
#     pass


# def as_int_when_value(cls):
#     """A decorator for the class `MeasurementOutcome` which makes is behave like an `int`
#     when the property `value` is not `None`.
#     """
#     def wrap_method(method_name):
#         """Returns a new method for the class given a method name"""
#         int_method = getattr(int, method_name)

#         def new_method(self, *args, **kwargs):
#             """Checks if the value is set, other raises an error"""
#             value = self.value
#             if value is None:
#                 raise NoValueError(f"The object '{repr(self)}' has no value yet, "
#                                    "consider flusing the current subroutine")
#             return int_method(value, *args, **kwargs)

#         return new_method

#     method_names = [
#         "__abs__",
#         "__add__",
#         "__and__",
#         "__bool__",
#         "__ceil__",
#         "__divmod__",
#         "__eq__",
#         "__float__",
#         "__floor__",
#         "__floordiv__",
#         "__ge__",
#         "__gt__",
#         "__hash__",
#         "__int__",
#         "__invert__",
#         "__le__",
#         "__lshift__",
#         "__lt__",
#         "__mod__",
#         "__mul__",
#         "__ne__",
#         "__neg__",
#         "__or__",
#         "__pos__",
#         "__pow__",
#         "__radd__",
#         "__rand__",
#         "__rdivmod__",
#         "__rfloordiv__",
#         "__rlshift__",
#         "__rmod__",
#         "__rmul__",
#         "__ror__",
#         "__round__",
#         "__rpow__",
#         "__rrshift__",
#         "__rshift__",
#         "__rsub__",
#         "__rtruediv__",
#         "__rxor__",
#         "__sub__",
#         "__truediv__",
#         "__xor__",
#         "bit_length",
#         "conjugate",
#         "denominator",
#         "imag",
#         "numerator",
#         "real",
#         "to_bytes",
#     ]
#     for method_name in method_names:
#         setattr(cls, method_name, wrap_method(method_name))
#     return cls


# @as_int_when_value
# class MeasurementOutcome(int):
#     @classmethod
#     def __new__(cls, *args, **kwargs):
#         return int.__new__(cls, 0)

#     def __init__(self, connection, array, index):
#         self._value = None
#         self._connection = connection
#         self._array = array
#         self._index = index

#     def __str__(self):
#         value = self.value
#         if value is None:
#             return (f"Measurement outcome to be stored in array with address "
#                     f"{self._array.address} at index {self._index}.\n"
#                     "To access the value, the subroutine must first be executed which can be done by flushing.")
#         else:
#             return str(value)

#     def __repr__(self):
#         return f"{self.__class__} with value={self.value}"

#     @property
#     def value(self):
#         if self._array is not None:
#             return self._value
#         if self._array is None:
#             raise NoValueError("Measurement outcome was not assigned an array, "
#                                "to use a measure outcome give it an address and index when calling measure, e.g.:\n"
#                                "\narray = connection.new_array(1)"
#                                "\tm = q.measure(array=array, index=0)")
#         if not isinstance(self._index, int):
#             raise NonConstantIndexError("index is not constant and cannot be resolved")
#         value = self._connection._shared_memory._get_array_entry(address=self._address, index=self._index)
#         if value is not None:
#             self._value = value
#         return value

from netqasm.sdk.futures import Future


class MeasurementOutcome(Future):
    pass
