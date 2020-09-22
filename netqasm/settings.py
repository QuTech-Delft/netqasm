import os
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


BACKEND_ENV = "NETQASM_BACKEND"


def set_backend(backend):
    os.environ[BACKEND_ENV] = Backend(backend).value


def get_backend():
    backend = os.environ.get(BACKEND_ENV)
    if backend is None:
        return _default_backend()
    else:
        return Backend(backend)


def _default_backend():
    return Backend.NETSQUID
