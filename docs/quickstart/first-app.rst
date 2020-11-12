.. _first-app:

Running your first app
======================

Before writing our own application we will see how we can execute a pre-defined one on the simulator `NetSquid`_.
Make sure you first followed the previous parts and have the relevant packages installed.

Creating an application folder
------------------------------
Well first create an applicaton folder using a template.
Do this by running:

.. code-block:: bash
   
   netqasm new my-app

You can replace ``my-app`` with another name.
What's important is that this directiory cannot exist in your current working directory, since it will be created.
Go into the directory and see what files was created

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
What's perhaps even more exiting is that you will soon be able to execute this application without changing the files on real quantum hardware using our XXX which is work in progress.

.. warning::

   TODO update XXX with what we will call it, and provide link?

Inspecting the results
----------------------


Other pre-defined apps
----------------------
You have just simulated an application which teleports a qubit.
In :ref:`using-sdk` you will learn how to write your own.
However, before that, there are also other pre-defined applications you can easily instantiate and execute using the ``--app`` flag to ``netqasm new``.
Type ``netqasm new --help`` for a complete list.
To for example try out an application which performs anonymous transmission of a qubit, do:

.. code-block:: bash
   
   netqasm new my-anonymous-app --app=anonymous_transmission

Using other simulators
----------------------


.. _NetSquid: https://netsquid.org/
