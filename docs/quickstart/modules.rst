.. _sdk-objects:

SDK objects
===========

Described below are the user-exposed components of the NetQASM SDK.

* :class:`~.BaseNetQASMConnection`
* :class:`~qubit.Qubit`
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
These different classes expose the same set of functionalities.
They only differ in the way they communicate with the underlying simulator.
For more details see :ref:`first-app`.

.. TODO Add link to SquidASM.
.. _NetSquid: https://netsquid.org/

NetQASM connection
------------------

.. automodule:: netqasm.sdk.connection
   :noindex:

   .. autoclass:: BaseNetQASMConnection
      :noindex:
      :special-members: __enter__, __exit__
      :members: app_name, node_name, app_id, flush, block

Qubit
-----

.. automodule:: netqasm.sdk.qubit
   :noindex:

   .. autoclass:: Qubit
      :noindex:
      :members: qubit_id, entanglement_info, remote_entangled_node, measure,
                X, Y, Z, H, S, K, T,
                rot_X, rot_Y, rot_Z,
                cnot, cphase, reset, free

EPR socket
----------

.. automodule:: netqasm.sdk.epr_socket
   :noindex:

   .. autoclass:: EPRSocket
      :members: conn, remote_app_name, remote_node_id, epr_socket_id, remote_epr_socket_id, min_fidelity,
                create, recv,
      :noindex:

      .. automethod:: create_context(number=1, sequential=False)
         :noindex:

      .. automethod:: recv_context(number=1, sequential=False)
         :noindex:

Futures
-------

.. automodule:: netqasm.sdk.futures
   :noindex:

   .. autoclass:: Future
      :members: add, value
      :noindex:

   .. autoclass:: Array
      :members: get_future_index, get_future_slice, foreach, enumerate
      :noindex:

   .. autoclass:: RegFuture
      :members: add, value
      :noindex:


Classical communication
-----------------------

.. automodule:: netqasm.sdk.classical_communication.socket
   :members: Socket
   :noindex:
