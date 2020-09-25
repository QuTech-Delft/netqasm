import os
from enum import Enum


class Simulator(Enum):
    NETSQUID = "netsquid"
    SIMULAQRON = "simulaqron"


class Formalism(Enum):
    STAB = "stab"
    KET = "ket"
    DM = "dm"


class Flavour(Enum):
    VANILLA = "vanilla"
    NV = "nv"


SIMULATOR_ENV = "NETQASM_SIMULATOR"


def set_simulator(simulator):
    os.environ[SIMULATOR_ENV] = Simulator(simulator).value


def get_simulator():
    simulator = os.environ.get(SIMULATOR_ENV)
    if simulator is None:
        return _default_simulator()
    else:
        return Simulator(simulator)


def _default_simulator():
    return Simulator.NETSQUID
