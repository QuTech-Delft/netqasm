import abc


class NetworkInfo:
    @classmethod
    @abc.abstractmethod
    def _get_node_id(cls, node_name: str) -> int:
        """Returns the node id for the node with the given name"""
        # Should be subclassed
        pass

    @classmethod
    @abc.abstractmethod
    def _get_node_name(cls, node_id: int) -> str:
        """Returns the node name for the node with the given ID"""
        # Should be subclassed
        pass

    @classmethod
    @abc.abstractmethod
    def get_node_id_for_app(cls, app_name: str) -> int:
        """Returns the node id for the app with the given name"""
        # Should be subclassed
        pass

    @classmethod
    @abc.abstractmethod
    def get_node_name_for_app(cls, app_name: str) -> str:
        """Returns the node name for the app with the given name"""
        # Should be subclassed
        pass
