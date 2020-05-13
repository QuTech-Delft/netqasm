import abc
from dataclasses import dataclass


# Number of elements in a create request etc
CREATE_FIELDS = 20
OK_FIELDS = 9


@dataclass(eq=True, frozen=True)
class Address:
    node_id: int
    epr_socket_id: int


class BaseNetworkStack(abc.ABC):
    @abc.abstractmethod
    def put(self, request):
        """Handles an request to the network stack"""
        pass

    @abc.abstractmethod
    def setup_epr_socket(self, epr_socket_id, remote_node_id, remote_epr_socket_id, timeout=1):
        """Asks the network stack to setup circuits to be used"""
        pass
