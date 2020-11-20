.. _first-app:

Running your first app
======================

Before writing our own application we will see how we can execute a pre-defined one on the simulator :netsquid:`NetSquid <>`.
Make sure you first followed the previous parts and have the relevant packages installed.

Creating an application folder
------------------------------
We'll first create an applicaton folder using a template.
Do this by running:

.. code-block:: bash
   
   netqasm new my-app

You can replace ``my-app`` with another name.
What's important is that this directiory cannot exist in your current working directory, since it will be created.
Go into the directory and see what files were created.

.. code-block:: bash
   
   cd my-app
   ls

You will see two files ``app_sender.py`` and ``app_receiver.py``.
These are the files defining the application itself.
There are two parties in this application: ``sender`` and ``recevier``, but you can have an arbitary number of parties.
Each party is associated with a specific node in the network by the `roles.yaml` file.
Furthermore, the network is specified in the file `network.yaml`.
Lastly, the ``sender.yaml`` and ``recevier.yaml`` defines input to the application.
For more details about these files and how to configure them, see :ref:`file-structure`.

Running the app
---------------
Before describing what the application does and how you can change it, lets just run it and see what happens.
To do this, type

.. code-block:: bash
   
   netqasm simulate

which, if everything went well, will print some information about a ``sender`` and a ``recevier``.
What this application in fact does is to teleport a qubit from the ``sender`` to the ``recevier``.
We will go through how this works more in detail in :ref:`using-sdk`.
Amazing, you have just teleported qubit over a simulated quantum network.
What's perhaps even more exiting is that you will soon be able to execute this application without changing the files on real quantum hardware using our Web SDK which is work in progress.

.. warning::

   TODO provide link to Web SDK?

To see what options the CLI tool takes, do:

.. code-block:: bash
   
   netqasm simulate --help

You can for example increase the amount of logging shown by ``--log-level=INFO`` (or ``DEBUG``) or use a different qubit representation in the simulation by ``--formalism=dm`` to use density matrix.
As described below you can also use a different simulator.

Inspecting the results
----------------------
You may have seen that after running the application a new directory has appeared: ``log``.
This is were all the results of the simulation get stored.
Each execution of the application creates a new directory in ``log`` using a timestamp.
For convenience, a copy of this folder is also created with the name ``LAST``.
The files in the log-folder contain information what happened during the simulation: what quantum operations were applied, what classical messages were sent, what entangled pairs were created and what the outcome of the application was.
This is further detailed in :ref:`file-structure`.


Other pre-defined apps
----------------------
You have just simulated an application which teleports a qubit.
In :ref:`using-sdk` you will learn how to write your own.
However, before that, there are also other pre-defined applications you can easily instantiate and execute using the ``--template`` flag to ``netqasm new``.
Type ``netqasm new --help`` for a complete list.
To for example try out an application which performs anonymous transmission of a qubit, do:

.. code-block:: bash
   
   netqasm new my-anonymous-app --template=anonymous_transmission

Using other simulators
----------------------
Above we have simulated an application which teleports a qubit over a quantum network using the simulator :netsquid:`NetSquid <>`.
You can easily run the same application using another supported simulator.
For example to use :simulaqron:`SimulaQron <>` instead, simply do:

.. code-block:: bash

   netqasm simulate --simulator=simulaqron

.. note::

   For this to work you need simulaqron installed, otherwise the CLI will tell you that ``ModuleNotFoundError: to use simulaqron as simulator, `simulaqron` needs to be installed``.
   SimulaQron can be installed using pip by

   .. code-block:: bash

      pip install simulaqron
