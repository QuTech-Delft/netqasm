_MEMORIES = {}


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

    def __setitem__(self, index, value):
        self._assert_within_width(value)
        self._memory[index] = value

    def __getitem__(self, index):
        return self._memory[index]

    def _assert_within_width(self, value):
        min_value = -2**self.width
        max_value = 2**self.width - 1
        if not min_value <= value <= max_value:
            raise OverflowError("value {value} does not fit into {self.width} bits")
