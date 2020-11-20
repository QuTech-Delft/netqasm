.. _installation:

Installation
============

Using pip
---------

To install netqasm do

.. code-block:: bash

   pip install netqasm


To simulate a set of application files using a simulator, additional packages are required.
Currently supported simulators  are:

* :netsquid:`NetSquid <>`: Requires ``netsquid`` and :squidasm:`SquidASM <>` installed.
  For how to install ``netsquid``, see https://netsquid.org/#registration.
  :squidasm:`SquidASM <>` can be installed using pip by (requires ``netsquid`` to already be installed)

   .. code-block:: bash

      pip install squidasm

* :simulaqron:`SimulaQron <>`: Requires only ``simulaqron`` which can be installed using pip by

   .. code-block:: bash

      pip install simulaqron


.. _NetSquid: https://netsquid.org/
.. _SimulaQron: http://www.simulaqron.org/
.. _SquidASM: https://gitlab.com/softwarequtech/netqasm/squidasm

From source
-----------
To install netqasm from source, clone this repo and run

.. code-block:: bash
   
   make install

To verify the installation, do:

.. code-block:: bash

   make verify
