import abc
from dataclasses import dataclass
from typing import Any, Generator, Union

from qlink_interface import (
    LinkLayerCreate,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerRecv,
)

# Number of elements in a create request etc
# NOTE minus 2 since remote_node_id and epr_socket_id comes as immediates
CREATE_FIELDS = len(LinkLayerCreate._fields) - 2
OK_FIELDS_K = len(LinkLayerOKTypeK._fields)
OK_FIELDS_M = len(LinkLayerOKTypeM._fields)


@dataclass(eq=True, frozen=True)
class Address:
    node_id: int
    epr_socket_id: int


class BaseNetworkStack(abc.ABC):
    @abc.abstractmethod
    def put(self, request: Union[LinkLayerCreate, LinkLayerRecv]) -> None:
        """Handles an request to the network stack"""
        # NOTE: LinkLayerRecv is currently not used at all
        pass

    @abc.abstractmethod
    def setup_epr_socket(
        self,
        epr_socket_id: int,
        remote_node_id: int,
        remote_epr_socket_id: int,
        timeout: float = 1.0,
    ) -> Generator[Any, None, None]:
        """Asks the network stack to setup circuits to be used"""
        pass

    @abc.abstractmethod
    def get_purpose_id(self, remote_node_id: int, epr_socket_id: int) -> int:
        pass
