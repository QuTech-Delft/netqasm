from netqasm.encoding import ADDRESS_BITS, REG_INDEX_BITS, RegisterName

_MEMORIES = {}


def reset_memories():
    for key in list(_MEMORIES.keys()):
        _MEMORIES.pop(key)


def get_shared_memory(node_name, key=None):
    absolute_key = (node_name, key)
    memory = _MEMORIES.get(absolute_key)
    if memory is None:
        memory = SharedMemory()
        _MEMORIES[absolute_key] = memory
    return memory


def _assert_within_width(value, width):
    min_value = -(2**(width - 1))
    max_value = 2**(width - 1) - 1
    if not min_value <= value <= max_value:
        raise OverflowError("value {value} does not fit into {width} bits")


class Register:
    def __init__(self):
        self._size = 2 ** REG_INDEX_BITS
        self._register = {}

    def __len__(self):
        return self._size

    def __str__(self):
        return str(self._register)

    def __setitem__(self, index, value):
        self._assert_within_length(index)
        _assert_within_width(value, ADDRESS_BITS)
        self._register[index] = value

    def __getitem__(self, index):
        self._assert_within_length(index)
        return self._register.get(index)

    def _assert_within_length(self, index):
        if not (0 <= index < len(self)):
            raise IndexError(f"index {index} is not within 0 and {len(self)}")


def setup_registers():
    return {reg_name: Register() for reg_name in RegisterName}


class Arrays:
    def __init__(self):
        self._arrays = {}

    def __str__(self):
        return str(self._arrays)

    def __setitem__(self, key, value):
        address, index = self._extract_key(key)
        if isinstance(index, int):
            _assert_within_width(value, ADDRESS_BITS)
            _assert_within_width(index, ADDRESS_BITS)
        elif isinstance(index, slice):
            self._assert_list(value)
            if index.start is not None:
                _assert_within_width(index.start, ADDRESS_BITS)
            if index.stop is not None:
                _assert_within_width(index.stop, ADDRESS_BITS)
        else:
            raise TypeError(f"Cannot use {key} of type {type(key)} as an index")
        array = self._get_array(address)
        try:
            if isinstance(index, slice):
                assert len(array[index]) == len(value), "value not of correct length"
            array[index] = value
        except IndexError:
            raise IndexError(f"index {index} is out of range for array with address {address}")

    def __getitem__(self, key):
        address, index = self._extract_key(key)
        array = self._get_array(address)

        try:
            value = array[index]
        except IndexError:
            raise IndexError(f"index {index} is out of range for array with address {address}")
        return value

    def _get_array(self, address):
        if address not in self._arrays:
            raise IndexError(f"No array with address {address}")
        return self._arrays[address]

    def _set_array(self, address, array):
        if address not in self._arrays:
            raise IndexError(f"No array with address {address}")
        self._arrays[address] = array

    def has_array(self, address):
        return address in self._arrays

    @staticmethod
    def _extract_key(key):
        try:
            address, index = key
        except (TypeError, ValueError):
            raise ValueError("Can only access entries and slices of arrays, not the full array")
        _assert_within_width(address, ADDRESS_BITS)
        return address, index

    @staticmethod
    def _assert_list(value):
        if not isinstance(value, list):
            raise TypeError(f"expected 'list', not {type(value)}")
        for x in value:
            _assert_within_width(x, ADDRESS_BITS)
        _assert_within_width(len(value), ADDRESS_BITS)

    def init_new_array(self, address, length):
        if address in self._arrays:
            raise ValueError(f"Array already initialized at address {address}")
        _assert_within_width(address, ADDRESS_BITS)
        self._arrays[address] = [None] * length


class SharedMemory:

    def __init__(self):
        self._registers = setup_registers()
        self._arrays = Arrays()

    def __getitem__(self, key):
        if isinstance(key, Register):
            return self.get_register(key)
        elif isinstance(key, tuple):
            address, index = key
            return self.get_array_part(address, index)
        elif isinstance(key, int):
            return self._get_array(key)

    def get_register(self, register):
        return self._registers[register.name][register.index]

    def set_register(self, register, value):
        self._registers[register.name][register.index] = value

    def get_array_part(self, address, index):
        return self._arrays[address, index]

    def set_array_part(self, address, index, value):
        self._arrays[address, index] = value

    def _get_array(self, address):
        return self._arrays._get_array(address)

    def init_new_array(self, address, length=1, new_array=None):
        if new_array is None:
            self._arrays.init_new_array(address, length)
        else:
            if not self._arrays.has_array(address):
                self._arrays.init_new_array(address, len(new_array))
            self._arrays._set_array(address, new_array)
