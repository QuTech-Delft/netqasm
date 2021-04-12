import abc


class NetworkInfo:
    """Global information about the current quantum network environment.

    This class is a container for static functions that provide information about
    the current network setting.
    Applications may use this information to e.g. obtain node IDs or map party names
    to nodes.

    Concrete runtime contexts (like a simulator, or a real hardware setup) should
    override these methods to provide the information specific to that context.
    """

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
