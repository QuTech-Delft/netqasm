SDK objects
===========

Described below are the user-exposed components of the NetQASM SDK.

* :class:`~.BaseNetQASMConnection`
* :class:`~.Qubit`
* :class:`~.EPRSocket`
* Futures:

   * :class:`~.Future`
   * :class:`~.Array`
   * :class:`~.RegFuture`

* :class:`~.Socket`

Note that :class:`~.BaseNetQASMConnection` and :class:`.Socket` are abstract base-classes.
These are implemented specifically for a runtime, e.g. a simulator or hardware runtime.
However, when using the SDK this is handled automatically if these are imported from :mod:`netqasm.sdk.external`.
For example one might write an application as follows

.. code-block:: python

   from netqasm.sdk.external import NetQASMConnection, Socket

   # Setup a classical socket
   bob_socket = Socket("alice", "bob")

   with NetQASMConnection('alice'):
      # Main application...

The classes :class:`~.NetQASMConnection` and :class:`~.Socket` will be different subclasses of the abstract classes, depending on which runtime is used.
If for example the application is simulated using `SquidASM`_ and `NetSquid`_, then the :class:`NetQASMConnection` will in fact be the class `squidasm.sdk.NetSquidConnection`.
For more details see :ref:`cli`.

.. TODO Add link to SquidASM.
.. _NetSquid: https://netsquid.org/

NetQASM connection
------------------

.. automodule:: netqasm.sdk.connection

   .. autoclass:: BaseNetQASMConnection
      :special-members: __enter__, __exit__
      :members: app_name, node_name, app_id, flush, block

Qubit
-----

.. automodule:: netqasm.sdk.qubit

   .. autoclass:: Qubit
      :members: qubit_id, entanglement_info, remote_entangled_node, measure,
                X, Y, Z, H, S, K, T,
                rot_X, rot_Y, rot_Z,
                cnot, cphase, reset, free

EPR socket
----------

.. automodule:: netqasm.sdk.epr_socket

   .. autoclass:: EPRSocket
      :members: conn, remote_app_name, remote_node_id, epr_socket_id, remote_epr_socket_id, min_fidelity,
                create, recv,

      .. automethod:: create_context(number=1, sequential=False)

      .. automethod:: recv_context(number=1, sequential=False)

Futures
-------

.. automodule:: netqasm.sdk.futures

   .. autoclass:: Future
      :members: add, value

   .. autoclass:: Array
      :members: get_future_index, get_future_slice, foreach, enumerate

   .. autoclass:: RegFuture
      :members: add, value


Classical communication
-----------------------

.. automodule:: netqasm.sdk.classical_communication.socket
   :members: Socket
