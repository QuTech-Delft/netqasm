from enum import Enum


class Backend(Enum):
    NETSQUID = "netsquid"
    SIMULAQRON = "simulaqron"


class Formalism(Enum):
    STAB = "stab"
    KET = "ket"
    DM = "dm"


class Flavour(Enum):
    VANILLA = "vanilla"
    NV = "nv"


_BACKEND = [Backend.NETSQUID]


def set_backend(backend):
    _BACKEND[0] = Backend(backend)


def get_backend():
    return _BACKEND[0]
