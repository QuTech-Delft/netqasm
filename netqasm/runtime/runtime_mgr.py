from abc import abstractmethod


class NetworkInstance:
    pass


class NetworkConfig:
    pass


class ApplicationInstance:
    pass


class ApplicationOutput:
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
