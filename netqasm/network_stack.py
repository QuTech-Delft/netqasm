import abc
from dataclasses import dataclass
from typing import List


# Number of elements in a create request etc
CREATE_FIELDS = 20
OK_FIELDS = 9


@dataclass(eq=True, frozen=True)
class Rule:
    remote_node_id: int
    purpose_id: int


@dataclass
class CircuitRules:
    recv_rules: List[Rule]
    create_rules: List[Rule]


class BaseNetworkStack(abc.ABC):
    @abc.abstractmethod
    def put(self, request):
        """Handles an request to the network stack"""
        pass

    @abc.abstractmethod
    def setup_circuits(self, circuit_rules):
        """Asks the network stack to setup circuits to be used"""
        pass
