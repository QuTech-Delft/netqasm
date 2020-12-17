from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any


class QuantumHardware(Enum):
    Generic = "Generic"
    NV = "NV"
    TrappedIon = "TrappedIon"


class NoiseType(Enum):
    NoNoise = "NoNoise"
    Depolarise = "Depolarise"
    DiscreteDepolarise = "DiscreteDepolarise"
    Bitflip = "Bitflip"


@dataclass
class Qubit:
    id: int
    t1: float
    t2: float


@dataclass
class Node:
    name: str
    hardware: QuantumHardware
    qubits: List[Qubit]
    gate_fidelity: float = 1.0


@dataclass
class Link:
    name: str
    node_name1: str
    node_name2: str
    noise_type: NoiseType
    fidelity: float


# Network configuration.
@dataclass
class NetworkConfig:
    nodes: List[Node]
    links: List[Link]


_DEFAULT_NUM_QUBITS = 5


# Create a config for a fully connected network where the nodes
# have the same names as the apps.
def default_network_config(app_names: List[str]) -> NetworkConfig:
    nodes = []
    links = []
    for name in app_names:
        qubits = [Qubit(id=i, t1=0, t2=0) for i in range(_DEFAULT_NUM_QUBITS)]
        node = Node(
            name=name,
            hardware=QuantumHardware.Generic,
            qubits=qubits,
            gate_fidelity=1
        )
        nodes += [node]

        for other_name in app_names:
            if other_name == name:
                continue
            link = Link(
                name=f"link_{name}_{other_name}",
                node_name1=name,
                node_name2=other_name,
                noise_type=NoiseType.NoNoise,
                fidelity=1
            )
            links += [link]

    return NetworkConfig(nodes, links)


# Build a NetworkConfig object from a dict that is created by reading a yaml file.
def parse_network_config(cfg) -> NetworkConfig:
    try:
        node_cfgs = cfg['nodes']
        link_cfgs = cfg['links']

        nodes = []
        for node_cfg in node_cfgs:
            qubit_cfgs = node_cfg['qubits']
            qubits = []
            for qubit_cfg in qubit_cfgs:
                qubit = Qubit(
                    id=qubit_cfg['id'],
                    t1=qubit_cfg['t1'],
                    t2=qubit_cfg['t2'],
                )
                qubits += [qubit]
            hardware = node_cfg.get('hardware', QuantumHardware.Generic)

            node = Node(
                name=node_cfg['name'],
                hardware=hardware,
                qubits=qubits,
                gate_fidelity=node_cfg['gate_fidelity']
            )
            nodes += [node]

        links = []
        for link_cfg in link_cfgs:
            link = Link(
                name=link_cfg['name'],
                node_name1=link_cfg['node_name1'],
                node_name2=link_cfg['node_name2'],
                noise_type=link_cfg['noise_type'],
                fidelity=link_cfg['fidelity']
            )
            links += [link]
    except KeyError as e:
        raise ValueError(f"Invalid network configuration: key not found: {e}")

    return NetworkConfig(nodes, links)


# Role-node configuration.
# Keys are role names, values are node names.
RolesConfig = Dict[str, str]


# App input per role.
# Keys are names of variables that are passed to the role's `main` function.
AppInput = Dict[str, Any]
