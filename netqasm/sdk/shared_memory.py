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


class SharedMemory:

    DEFAULT_SIZE = 1000
    DEFAULT_WIDTH = 32

    def __init__(self, size=None, width=None):
        if size is None:
            self._size = self.DEFAULT_SIZE
        if width is None:
            self._width = self.DEFAULT_WIDTH

        self._memory = [None] * self.size

    @property
    def size(self):
        return self._size

    @property
    def width(self):
        return self._width

    def __len__(self):
        return self.size

    def __str__(self):
        return str(self._memory)

    def __setitem__(self, index, value):
        if isinstance(index, tuple):
            index, array_index = index
        else:
            array_index = None
        if not isinstance(value, list):
            self._assert_within_width(value)
        try:
            current = self._memory[index]
        except IndexError:
            raise IndexError(f"Trying to get a value at address {index} which is outside "
                             f"the size ({len(self)}) of the shared memory")
        if array_index is None:
            if not ((current is None) or isinstance(current, type(value))):
                raise RuntimeError(f"Expected an address ({index}) position containing an "
                                   f"{type(value)} or uninitialized, not {current}")
            self._memory[index] = value
        else:
            if not isinstance(current, list):
                raise RuntimeError(f"Expected an address ({index}) position containing a list, not {current}")
            try:
                current[array_index] = value
            except IndexError:
                raise IndexError(f"Index {array_index} is outside the array at address {index}")

    def __getitem__(self, index):
        if isinstance(index, tuple):
            index, array_index = index
        else:
            array_index = None
        try:
            current = self._memory[index]
        except IndexError:
            raise IndexError(f"Trying to get a value at address {index} which is outside "
                             f"the size ({len(self)}) of the shared memory")
        if array_index is None:
            return current
        else:
            if not isinstance(current, list):
                raise RuntimeError(f"Expected an address ({index}) position containing a list, not {current}")
            try:
                return current[array_index]
            except IndexError:
                raise IndexError(f"Index {array_index} is outside the array at address {index}")

    def _assert_within_width(self, value):
        min_value = -2**self.width
        max_value = 2**self.width - 1
        if not min_value <= value <= max_value:
            raise OverflowError("value {value} does not fit into {self.width} bits")
