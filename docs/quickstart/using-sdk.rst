.. _using-sdk:

Using the SDK
=============

In :ref:`first-app` we have seen how to execute applications on a simulated quantum network.
We will now learn how to write an application ourselves.
Below are a few sample applications which we will go through, ranging from a very simple application on a single node to a more complicated examples further on.

Writing a first application
---------------------------
We will now create an very simple `hello-world`-application which consists of a single node that creates a qubit, performs a Hadamard gate and measures the qubit.

Let's first create a new folder ``my-app``:

.. code-block:: bash
   
   mkdir my-app
   cd my-app

In this folder we will now create our application

.. code-block:: bash
   
   touch app_alice.py

Open the file ``app_alice.py`` in your favorite editor/IDE and add the following code

.. code-block:: python
   :caption: app_alice.py

   from netqasm.sdk.external import NetQASMConnection


   def main(app_config=None):
      # Setup a connection to QNodeOS
       with NetQASMConnection("alice", log_config=app_config.log_config) as alice:
           print("Started NetQASM connection to QNodeOS")

.. note::
   
   The reason ``NetQASMConnection`` is imported from ``netqasm.sdk.external`` is that the class used
   will depend on which simulator is specified. The information about which simulator is used is
   stored in the environement varible ``NETQASM_SIMULATOR``, and makes ``netqasm.sdk.external``
   load different classes depending on its value. What this allows us to do is to simulate an
   application on different simulators, without changing anything, even imports.

What this code does is to setup a connection to the underlying (simulated) ``QNodeOS`` which can handle the NetQASM-instructions.
More information about ``QNodeOS`` can be found :qnodeos:`here <>`.
You can already run this application by doing ``netqasm simulate``, and if everything was correct you will see the message being printed.

In the context of the connection, we can now create a qubit

.. code-block:: python
   :emphasize-lines: 2, 9
   :caption: app_alice.py

   from netqasm.sdk.external import NetQASMConnection
   from netqasm.sdk import Qubit


   def main(app_config=None):
      # Setup a connection to QNodeOS
       with NetQASMConnection("alice", log_config=app_config.log_config) as alice:
           # Create a qubit
           q = Qubit(alice)

Running the application now seems perhaps to not do anything.
To make sure that a qubit is actually created we can set the log-level to ``INFO``

.. code-block:: bash

   netqasm simulate --log-level=DEBUG

You will then see that a subroutine is flushed and handled by the :class:`~.SubroutineHandler`, which is a simplified version of a ``QNodeOS`` used in simulation.

Let's now perform a gate on the qubit and also measure it.

.. code-block:: python
   :emphasize-lines: 11, 13, 15
   :caption: app_alice.py

   from netqasm.sdk.external import NetQASMConnection
   from netqasm.sdk import Qubit


   def main(app_config=None):
      # Setup a connection to QNodeOS
       with NetQASMConnection("alice", log_config=app_config.log_config) as alice:
           # Create a qubit
           q = Qubit(alice)
           # Perform a Hadamard gate
           q.H()
           # Measure the qubit
           m = q.measure()
           # Print the outcome
           print(f"Outcome is: {m}")

Let's run this now (without setting the ``--log-level``-flag) and see what the outcome is.
Hmm, it doesn't print the outcome but rather says:

.. code-block:: text

   Outcome is: Future to be stored in array with address 0 at index 0.
   To access the value, the subroutine must first be executed which can be done by flushing. 

The reason this happens is because the operations specified are in fact not directly executed on the (simulated) quantum hardware.
Rather, they are buffered into a ``NetQASM``-subroutine, until the subroutine is flushed and sent to ``QNodeOS``.
Let's fix our code by adding an explicit ``flush`` before the ``print``.

.. code-block:: python
   :emphasize-lines: 15
   :caption: app_alice.py

   from netqasm.sdk.external import NetQASMConnection
   from netqasm.sdk import Qubit


   def main(app_config=None):
      # Setup a connection to QNodeOS
       with NetQASMConnection("alice", log_config=app_config.log_config) as alice:
           # Create a qubit
           q = Qubit(alice)
           # Perform a Hadamard gate
           q.H()
           # Measure the qubit
           m = q.measure()
           # Flush the current subroutine
           alice.flush()
           # Print the outcome
           print(f"Outcome is: {m}")

Running the application again will now either print ``Outcome is: 0`` or ``Outcome is: 1``.
Run it a few times to see the different outcomes.

.. note::

   A connection is automatically flushed whenever it goes out of scope.
   So in the above example we could have just as well done:

   .. code-block:: python
      :caption: app_alice.py

      from netqasm.sdk.external import NetQASMConnection
      from netqasm.sdk import Qubit


      def main(app_config=None):
         # Setup a connection to QNodeOS
          with NetQASMConnection("alice", log_config=app_config.log_config) as alice:
              # Create a qubit
              q = Qubit(alice)
              # Perform a Hadamard gate
              q.H()
              # Measure the qubit
              m = q.measure()
           # Print the outcome
           print(f"Outcome is: {m}")

.. tip::

   It is important to understand how the execution happens when running the application.
   Try adding some print statements in the application, turn on ``INFO``-logging and see if you
   can understand why the print-statements and logging-statements are in the other you see.

Creating entanglement between nodes
-----------------------------------
Let's now extend our application by adding another node ``bob`` and have the two nodes create entanglement with each other.

To do this we will need to setup an :network-layer:`EPR socket <>`.
We do this by instanciating an object of :class:`~.EPRSocket` and give this to the ``NetQASMConnection``.
Consider the following code-example for the node with role ``alice``:

.. code-block::
   :emphasize-lines: 2, 7, 12, 16
   :caption: app_alice.py

   from netqasm.sdk.external import NetQASMConnection
   from netqasm.sdk import EPRSocket


   def main(app_config=None):
       # Specify an EPR socket to bob
       epr_socket = EPRSocket("bob")

       alice = NetQASMConnection(
           "alice",
           log_config=app_config.log_config,
           epr_sockets=[epr_socket],
       )
       with alice:
           # Create an entangled pair using the EPR socket to bob
           q_ent = epr_socket.create()[0]
           # Measure the qubit
           m = q_ent.measure()
       # Print the outcome
       print(f"alice's outcome is: {m}")

The code for ``bob`` will be very similar, with the only difference being that ``bob`` `receives` an entangled pair by calling ``recv`` on the EPR socket object:

.. code-block::
   :emphasize-lines: 16
   :caption: app_bob.py

   from netqasm.sdk.external import NetQASMConnection
   from netqasm.sdk import EPRSocket


   def main(app_config=None):
       # Specify an EPR socket to bob
       epr_socket = EPRSocket("alice")

       bob = NetQASMConnection(
           "bob",
           log_config=app_config.log_config,
           epr_sockets=[epr_socket],
       )
       with bob:
           # Receive an entangled pair using the EPR socket to alice
           q_ent = epr_socket.recv()[0]
           # Measure the qubit
           m = q_ent.measure()
       # Print the outcome
       print(f"bob's outcome is: {m}")

Running this application files using ``netqasm simulate`` prints the outcomes of the two nodes.
Since by default no noise is used, their outcomes will always be equal.

.. tip::

   Checkout the documentation of :class:`~.EPRSocket` to see what arguments :meth:`~.EPRSocket.create` and :meth:`~.EPRSocket.recv` can take.
   For example you will see that a number of pairs can be specified, which is why these methods return a list of :class:`~.qubit.Qubit`-objects.
   Also checkout the methods :meth:`~.EPRSocket.create_context` and :meth:`~.EPRSocket.recv_context()`, which allows to specify what to do whenever a pair is generated, using a context.

Adding classical communication
------------------------------
Applications generally also need to communicate classicaly between nodes, to for example communicate measurement outcomes.
We will extend our example by having ``alice`` communicate her outcome to ``bob``.
``bob`` will use this outcome to possible apply a correction in order to make his qubit be in the state :math:`|0\rangle` in both cases.
Consider the following code-snippets for ``alice`` and ``bob``:

.. code-block::
   :emphasize-lines: 1, 7, 26
   :caption: app_alice.py

   from netqasm.sdk.external import NetQASMConnection, Socket
   from netqasm.sdk import EPRSocket


   def main(app_config=None):
       # Setup a classical socket to bob
       socket = Socket("alice", "bob", log_config=app_config.log_config)

       # Specify an EPR socket to bob
       epr_socket = EPRSocket("bob")

       alice = NetQASMConnection(
           "alice",
           log_config=app_config.log_config,
           epr_sockets=[epr_socket],
       )
       with alice:
           # Create an entangled pair using the EPR socket to bob
           q_ent = epr_socket.create()[0]
           # Measure the qubit
           m = q_ent.measure()
       # Print the outcome
       print(f"alice's outcome is: {m}")

       # Send the outcome to bob
       socket.send(str(m))

.. code-block::
   :emphasize-lines: 1, 7, 19, 26
   :caption: app_bob.py

   from netqasm.sdk.external import NetQASMConnection, Socket
   from netqasm.sdk import EPRSocket


   def main(app_config=None):
       # Setup a classical socket to alice
       socket = Socket("bob", "alice", log_config=app_config.log_config)

       # Specify an EPR socket to bob
       epr_socket = EPRSocket("alice")

       bob = NetQASMConnection(
           "bob",
           log_config=app_config.log_config,
           epr_sockets=[epr_socket],
       )
       with bob:
           # Receive an entangled pair using the EPR socket to alice
           q_ent = epr_socket.recv()[0]

           # Receive the outcome from alice
           m = int(socket.recv())

           # Apply correction depending on outcome
           if m == 1:
               q_ent.X()

           # Measure the qubit
           m = q_ent.measure()

       # Print the outcome
       print(f"bob's outcome is: {m}")

Running the above example we can see that the outcome of ``bob`` is always 0, independently of the outcome of ``alice``.

A more complex example
----------------------
We will now look at a more complicated example, where we will use quantum error correction to protect an entangled qubit from errors.
In this example we will use the most simple quantum error-correction code, namely the :repcode:`repition code <>` on three qubits.
Before implementing the actual quantum error-correction code, let's define how we want the main functions to look like.
On ``alice``'s side we will

#. Create encode the qubit
#. Randomly apply a bit-flip
#. Correct any error
#. Decode the qubit again.
#. Measure the qubit and print the outcome

.. code-block::
   :emphasize-lines: 15, 18-23, 26, 29
   :caption: app_alice.py

   def main(app_config=None):
       # Specify an EPR socket to bob
       epr_socket = EPRSocket("bob")

       alice = NetQASMConnection(
           "alice",
           log_config=app_config.log_config,
           epr_sockets=[epr_socket],
       )
       with alice:
           # Create an entangled pair using the EPR socket to bob
           q_ent = epr_socket.create()[0]

           # Encode into repitition code
           logical_qubit = encode(q_ent)

           # Randomly introduce a bit-flip
           if random.randint(0, 1):
               i = random.choice(range(3))
               print(f"applying bit flip on qubit {i}")
               # q = random.choice(logical_qubit)
               q = logical_qubit[i]
               q.X()

           # Correct a possible bit-flip
           correct(logical_qubit)

           # Decode back
           decode(logical_qubit)

           # Measure the qubit
           m = logical_qubit[0].measure()

       # Print the outcome
       print(f"alice's outcome is: {m}")

``bob`` on the other hand will simple measure his entangled qubit and print the outcome.

.. code-block::
   :caption: app_bob.py

   def main(app_config=None):
       # Specify an EPR socket to bob
       epr_socket = EPRSocket("alice")

       bob = NetQASMConnection(
           "bob",
           log_config=app_config.log_config,
           epr_sockets=[epr_socket],
       )
       with bob:
           # Receive an entangled pair using the EPR socket to alice
           q_ent = epr_socket.recv()[0]

           # Measure the qubit
           m = q_ent.measure()

       # Print the outcome
       print(f"bob's outcome is: {m}")

Let's now implement the functions: ``encode``, ``correct`` and ``decode``:

.. code-block:: python
   :caption: app_alice.py

   import random

   from netqasm.sdk.external import NetQASMConnection, Socket
   from netqasm.sdk import EPRSocket, Qubit, parity_meas, t_inverse, toffoli_gate

   def encode(qubit):
       """Encodes a qubit into a repitition code by intializing two more

       Parameters
       ----------
       qubit : :class:`~.Qubit`
           Qubit to be encoded

       Returns
       -------
       list : list of encoded qubits
       """
       conn = qubit.connection
       logical_qubit = [qubit, Qubit(conn), Qubit(conn)]
       for q in logical_qubit[1:]:
           logical_qubit[0].cnot(q)
       return logical_qubit

.. code-block:: python
   :caption: app_alice.py

   def correct(logical_qubit):
       """Tries to correct a bit flip

       Parameters
       ----------
       logical_qubit : list of :class:`~.Qubit`
       """
       # Check code syndromes
       s1 = parity_meas(logical_qubit, 'ZZI')
       s2 = parity_meas(logical_qubit, 'IZZ')

       print(f"syndrome is ({s1}, {s2})")
       if (s1, s2) == (0, 0):  # No error
           pass
       elif (s1, s2) == (0, 1):  # Error on third
           logical_qubit[2].X()
       elif (s1, s2) == (1, 0):  # Error on first qubit
           logical_qubit[0].X()
       else:  # Error on second qubit
           logical_qubit[1].X()

.. code-block:: python
   :caption: app_alice.py

   def decode(logical_qubit):
       """Decodes the repitition code on three qubits
       After the first qubit in the list will be the decode qubit.

       Parameters
       ----------
       logical_qubit : list of :class:`~.Qubit
       """
       for q in logical_qubit[1:]:
           logical_qubit[0].cnot(q)
           # Toffoli with first qubit as target
           toffoli_gate(*reversed(logical_qubit))

Let's now run our application and see what happens.
Hmm, we get an error.

.. tip::
   
   Try to figure out what goes wrong before reading the solution below.

Our mistake is that we are trying to use the outcomes ``s1`` and ``s2``, in the ``correct``-function, before the subroutine is flushed.
One way to solve this is to add a ``flush``-statement as follows:

.. code-block:: python
   :caption: app_alice.py

   def correct(logical_qubit):
       """Tries to correct a bit flip

       Parameters
       ----------
       logical_qubit : list of :class:`~.Qubit`
       """
       # Check code syndromes
       s1 = parity_meas(logical_qubit, 'ZZI')
       s2 = parity_meas(logical_qubit, 'IZZ')

       conn = logical_qubit[0].connection
       conn.flush()

       print(f"syndrome is ({s1}, {s2})")
       if (s1, s2) == (0, 0):  # No error
           pass
       elif (s1, s2) == (0, 1):  # Error on third
           logical_qubit[2].X()
       elif (s1, s2) == (1, 0):  # Error on first qubit
           logical_qubit[0].X()
       else:  # Error on second qubit
           logical_qubit[1].X()

The application now works :)
You can see that independently on which qubit the bit-flip might occur, ``alice`` and ``bob`` always receive the same outcome, meaning that our error-correction code is working.

However, there is something we can still improve.
Namely, we can avoid the call to ``flush`` and instead make use of classical logic in ``NetQASM`` and let this be handled by ``QNodeOS``.
The reason we would want to do this is that whenever a ``flush`` happens, extra communication between the ``Host`` and ``QNodeOS`` is needed, see our :netqasm-paper:`paper <>` for more details.
We can see this happen if we increase the logging.
Run the above example by ``netqasm simulate --log-level=INFO``, which will produce a lot of logging.
Importantly, you can see that ``alice`` submits two subroutines to ``QNodeOS`` and not only one.

In the next part we look at how to use simple built-in classical logic in ``NetQASM`` to minimize the communication needed between the ``Host`` and ``QNodeOS``.

Simple classical logic
----------------------
Let's now improve our ``correct``-function above by avoiding the call to flush and use the simple logic built-in to ``NetQASM``.
We can rewrite the function to instead do:

.. code-block:: python
   :caption: app_alice.py

   def correct2(logical_qubit):
       """Tries to correct a bit flip

       Parameters
       ----------
       logical_qubit : list of :class:`~.Qubit`
       """
       # Check code syndromes
       s1 = parity_meas(logical_qubit, 'ZZI')
       s2 = parity_meas(logical_qubit, 'IZZ')

       with s1.if_eq(0):
           with s2.if_eq(1):  # outcomes (0, 1) error on third qubit
               logical_qubit[2].X()
       with s1.if_eq(1):
           with s2.if_eq(0):  # outcomes (1, 0) error on first qubit
               logical_qubit[0].X()
           with s2.if_eq(1):  # outcomes (1, 1) error on second qubit
               logical_qubit[1].X()

If you now run the application with the update function and with ``INFO`` logging, you will see that ``alice`` only uses one subroutine.
What happens under the hood, is that these if-statements are compiled into branching instructions in the ``NetQASM``-language.

.. note::

   The current syntax, e.g. ``with s1.if_eq(0):`` might change.
   Ideally, we would be able to write plain Python-if-statements in the future.


.. tip::
   Checkout the documentation for :class:`~.Future`.
   This is what's returned when measuring a qubit and on which one can apply simple logical statements such as :meth:`~.Future.if_eq`.
   Could you instead for example use the methods :meth:`~.Future.if_ez` and :meth:`~.Future.if_nz`.

As a next step, you can read more about how to configure the simulation of the application, what network to use, noise etc, in the section :ref:`file-structure`.
In :ref:`sdk-objects` the main functions and classes to be used are documented.
For the full API of the package, refer to :ref:`api`.
Enjoy programming applications for a quantum internet!
