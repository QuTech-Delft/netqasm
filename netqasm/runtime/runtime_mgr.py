"""Runtime interface for simulators.

This module contains the RuntimeManager class which can be used as a base class by
simulators to handle setting up backends and running applications.
"""

from abc import abstractmethod

from netqasm.runtime.application import ApplicationOutput


class NetworkInstance:
    pass


class NetworkConfig:
    pass


class ApplicationInstance:
    pass


class RuntimeManager:
    @abstractmethod
    def start_backend(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_network(self) -> NetworkInstance:
        raise NotImplementedError

    @abstractmethod
    def set_network(self, cfg: NetworkConfig) -> None:
        raise NotImplementedError

    @abstractmethod
    def run_app(self, app: ApplicationInstance) -> ApplicationOutput:
        raise NotImplementedError
