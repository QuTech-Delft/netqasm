SHARED_MEMORY_SIZE = 1000

_MEMORIES = {}


def get_memory(node_name, key=None):
    absolute_key = (node_name, key)
    memory = _MEMORIES.get(absolute_key)
    if memory is None:
        memory = {}
        _MEMORIES[absolute_key] = memory
    return memory
