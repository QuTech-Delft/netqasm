.. _file-structure:

Application file structure
==========================

Application file structure

Applications are organized into directories:
all source code and configuration files relating to an application must be in the same directory.

An application directory consists of the following files:

* **Application source code**. These are Python source code files with names starting with `app_`, e.g. `app_alice.py`.
  There should be one file for each 'role' involved in the networked application.
* **Application input**. Each role can have a YAML file specifying the inputs to the application.
  Each role has its own local inputs.
  Names correspond the roles in the application. For example, the role 'sender' has an input file `sender.yaml`.
* **Network configuration**. A single YAML file `network.yaml` specifying characteristics of the simulated network.
  See below for a detailed description of the expected format.
* **Role-network mapping**. Roles are logical concepts related to the application, and not directly tied to a physical (simulated) node.
  In the `roles.yaml` file you can specify which role (i.e. which `app_XXX.py` file) runs on which network node.

.. tip::

   The `netqasm new` and `netqasm init` commands automatically create the above file types.

======================
File content format
======================

**Application source code**

Each `app_XXX.py` file should have a `main` function.

.. warning::

   TODO: expand or refer to SDK usage.


**Application input**

A `<role>.yaml` file should contain a simply key-value list of inputs.
For example:

.. code-block:: YAML
   
   theta: 3.1415
   x: 1


**Network configuration**


.. warning::

   TODO: maybe describe it using a `dataclass` class in the API?

**Role-network mapping**

The `roles.yaml` file should contain a simple list of key-value pairs.
Each key should be a role name and each value a node name occurring in the network configuration.


================
Results and logs
================
Running an application produces two kinds of output: **application results** and **log files**.

If it doesn't exist already, a `log` directory is automatically created in the application directory.
In it, for each run of the application, a directory is created with a name indicating the time it was generated, e.g. `20201117-104744`.
For convenience, the last directory is always copied into a directory called `LAST`, so in most cases you can just look into `log/LAST` for the relevant output.

The output files are the following:

* **Application results**. Application-specific results are written to `results.yaml`.
* **Instruction logs**. The simulator logs which NetQASM instructions it executes on each simulated node to a YAML file.
  For each node `XXX`, a file `XXX_instrs.yaml` is generated.
* **Network log**. Events related to the network and that are not local to one specific node are logged to `network_log.yaml`.
  These event currently only include entanglement generation events.
* **Classical communciation logs**. For each role XXX, a file `XXX_class_comm.yaml` is generated with all messages that are sent or received to/from that role.
* **Applicaton logs**. Applications can also log custom information to a file.
  An 'application log' from a role `XXX` ends up in `XXX_app_log.yaml`.


==========================
Output file content format
==========================

**Application results**

The `results.yaml` file contains the Python directory that is `return`ed at the end of the `main` function in the source code.
It lists these results for each of the roles in the application.

It also lists the returns values of the backend, if any. TODO: how and when?


**Instruction logs**

A `XXX_instr.yaml` contains a list of all NetQASM instructions that were executed by role `XXX`, in chronological order.

Each instruction log item has the following format:

.. warning::

   TODO: maybe describe it using a `dataclass` class in the API?


**Network log**

The `network_log.yaml` contains a list of all entanglement events that happened in the simulated network, in chronological order.

Each log item has the following format:

.. warning::

   TODO: maybe describe it using a `dataclass` class in the API?


**Classical communciation logs**

Each `XXX_class_comm.yaml` contains a list of all messages that were sent or received by role `XXX`, in chronological order.

Each log item has the following format:

.. warning::

   TODO: maybe describe it using a `dataclass` class in the API?


**Application logs**

Each `XXX_app_log.yaml` contains a list of custom log statements coming from `app_XXX.py`.
