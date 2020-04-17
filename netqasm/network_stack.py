import abc


# Number of elements in a create request etc
CREATE_FIELDS = 20
OK_FIELDS = 9


class BaseNetworkStack(abc.ABC):
    @abc.abstractmethod
    def put(self, request):
        """Handles an request to the network stack"""
        pass
