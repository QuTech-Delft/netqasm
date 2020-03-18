import abc


class BaseNetworkStack(abc.ABC):
    @abc.abstractmethod
    def put(self, request):
        """Handles an request to the network stack"""
        pass
