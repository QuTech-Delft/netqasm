.. _file-structure:

Application file structure
==========================

Applications are organized into directories:
all source code entry points and configuration files relating to an application must be in the same directory.

Quantum network applications typically involve multiple parties, each on a separate node in the network.
We refer to these parties as `roles`.
For example, a teleportation application might have two roles: a `sender` and a `receiver`.

An application directory consists of the following files:

* **Application source code**. These are Python source code files with names starting with ``app_``, e.g. ``app_alice.py``.
  There should be one file for each 'role' involved in the networked application.
* **Application input**. Each role can have a YAML file specifying the inputs to the application.
  Each role has its own local inputs.
  Names correspond the roles in the application. For example, the role 'sender' has an input file ``sender.YAML``.
* **Network configuration**. A single YAML file ``network.yaml`` specifying characteristics of the simulated network.
  See below for a detailed description of the expected format.
* **Role-network mapping**. Roles are logical concepts related to the application, and not directly tied to a physical (simulated) node.
  In the ``roles.yaml`` file you can specify which role (i.e. which ``app_<role>.py`` file) runs on which network node.

.. tip::

   The ``netqasm new`` and ``netqasm init`` commands automatically create the above file types.

======================
File content format
======================

+++++++++++++++++++++++
Application source code
+++++++++++++++++++++++

Each ``app_<role>.py`` file should have a ``main`` function.
See for more details :ref:`using-sdk`.


+++++++++++++++++
Application input
+++++++++++++++++

A ``<role>.yaml`` file should contain a simply dictionary of inputs.
For example:

.. code-block:: YAML
   
   theta: 3.1415
   x: 1


+++++++++++++++++++++
Network configuration
+++++++++++++++++++++

See the :class:`~.config.NetworkConfig` dataclass.

++++++++++++++++++++
Role-network mapping
++++++++++++++++++++

The ``roles.yaml`` file should contain a simple list of key-value pairs.
Each key should be a role name and each value a node name occurring in the network configuration.


================
Results and logs
================
Running an application produces two kinds of output: **application results** and **log files**.

If it doesn't exist already, a ``log`` directory is automatically created in the application directory.
In it, for each run of the application, a directory is created with a name indicating the time it was generated, e.g. ``20201117-104744``.
For convenience, the last directory is always copied into a directory called ``LAST``, so in most cases you can just look into ``log/LAST`` for the relevant output.

The output files are the following:

* **Application results**. Application-specific results are written to ``results.yaml``.
* **Instruction logs**. The simulator logs which NetQASM instructions it executes on each simulated node to a YAML file.
  For each ``<node>``, a file ``<node>_instrs.yaml`` is generated.
* **Network log**. Events related to the network and that are not local to one specific node are logged to ``network_log.yaml``.
  These event currently only include entanglement generation events.
* **Classical communciation logs**. For each ``<role>``, a file ``<role>_class_comm.yaml`` is generated with all messages that are sent or received to/from that role.
* **Applicaton logs**. Applications can also log custom information to a file.
  An 'application log' from a ``<role>`` ends up in ``<role>_app_log.yaml``.


====================
Output file contents
====================

+++++++++++++++++++
Application results
+++++++++++++++++++

The ``results.yaml`` file contains the Python directories that are ``return`` ed at the end of the ``main``
function in each role's source code.


++++++++++++++++
Instruction logs
++++++++++++++++

A ``<role>_instr.yaml`` contains a list of all NetQASM instructions that were executed by ``<role>``, in chronological order.

Each log statement includes the instruction type, and the time at which it was executed.
It also includes the states of the qubits in the network (across all nodes) and which of these are entangled or not.
Entangled qubits appear in the same `qubit group`.

This information is about the states directly `after` the instruction is executed.

See the :class:`~.logging.InstrLogEntry` dataclass for the format of each log entry.


+++++++++++
Network log
+++++++++++

The ``network_log.yaml`` contains a list of all entanglement events that happened in the simulated network, in chronological order.
As in the instruction log, the qubit states and groups are given as they are immediately `after` the event.

Two events (called `stages`) exist: ``START`` (entanglement generation has started) and ``FINISH`` (entanglement has successfully been generated).

Furtermore, there are two `types` of entanglement generation: 

  * ``MD`` (Measure Directly): upon successful generation, immediately measure the two (one in each node) qubits.
    So, directly after a ``FINISH`` event of type ``MD``, the corresponding qubits do not appear in the qubit information.
  * ``CK`` (Create and Keep): upon successful generation, keep the qubits alive.
    The corresponding qubits appear in the qubit group information, and are (obviously) entangled.

``START`` events do `not` give information about the `type`. This is only given at ``FINISH`` events.

``MD`` events (at the ``FINISH`` stage) have additional information ``BAS`` and ``MSR``.
These are the bases (one for each node) used for the (immediate) mesaurement, and the mesaurement outcomes themselves.

See the :class:`~.logging.NetworkLogEntry` dataclass for the format of each log entry.


++++++++++++++++++++++++++++
Classical communciation logs
++++++++++++++++++++++++++++

Each ``<role>_class_comm.yaml`` contains a list of all messages that were sent or received by ``<role>``, in chronological order.

See :class:`~.logging.ClassCommLogEntry` dataclass for the format of each log entry.


++++++++++++++++
Application logs
++++++++++++++++

Each ``<role>_app_log.yaml`` contains a list of custom log statements coming from ``app_<role>.py``.
