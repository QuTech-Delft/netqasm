import abc


class NetworkInfo:
    @abc.abstractclassmethod
    def _get_node_id(cls, node_name):
        """Returns the node id for the node with the given name"""
        # Should be subclassed
        pass

    @abc.abstractclassmethod
    def _get_node_name(cls, node_id):
        """Returns the node name for the node with the given ID"""
        # Should be subclassed
        pass

    @abc.abstractclassmethod
    def get_node_id_for_app(cls, app_name):
        """Returns the node id for the app with the given name"""
        # Should be subclassed
        pass

    @abc.abstractclassmethod
    def get_node_name_for_app(cls, app_name):
        """Returns the node name for the app with the given name"""
        # Should be subclassed
        pass
