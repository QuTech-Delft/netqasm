"""
Network stack interface for simulators.

This module provides the `BaseNetworkStack` class which can be used by simulators
as a base class for modeling the network stack.
"""

import abc
from dataclasses import dataclass
from typing import Any, Generator, Union

from netqasm.qlink_compat import (
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
    """Base class for a (extremly simplified) network stack in simulators.

    This class can be used as a simplified network stack that can handle requests
    that adhere to the QLink-Interface.
    """

    @abc.abstractmethod
    def put(self, request: Union[LinkLayerCreate, LinkLayerRecv]) -> None:
        """Put a link layer request to the network stack"""
        pass

    @abc.abstractmethod
    def setup_epr_socket(
        self,
        epr_socket_id: int,
        remote_node_id: int,
        remote_epr_socket_id: int,
        timeout: float = 1.0,
    ) -> Generator[Any, None, None]:
        """Ask the network stack to open an EPR socket."""
        pass

    @abc.abstractmethod
    def get_purpose_id(self, remote_node_id: int, epr_socket_id: int) -> int:
        pass
