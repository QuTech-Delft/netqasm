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

* :squidasm:`SquidASM <>`: Requires ``netsquid`` and :squidasm:`SquidASM <>` installed.
  For how to install ``netsquid``, see https://netsquid.org/#registration.
  :squidasm:`SquidASM <>` can be installed using pip while supplying your NetSquid account information:

   .. code-block:: bash

      pip install squidasm --extra-index-url=https://{netsquid-user-name}:{netsquid-password}@pypi.netsquid.org

* :simulaqron:`SimulaQron <>`: Requires only ``simulaqron`` which can be installed using pip by

   .. code-block:: bash

      pip install simulaqron
   
   SimulaQron itself needs a backend to be installed in order to run simulations. One of the supported backends is ProjectQ.
   To install ProjectQ, do:

   .. code-block:: bash

      pip install projectq


.. _NetSquid: https://netsquid.org/
.. _SimulaQron: http://www.simulaqron.org/
.. _SquidASM: https://github.com/QuTech-Delft/squidasm
.. _Quantum Network Explorer: https://www.quantum-network.com/

.. note::

   If you have trouble installing one of the packages above, it may be that
   you first need to install the `wheel` package, by ``pip install wheel``.

From source
-----------
To install netqasm from source, clone this repo and run

.. code-block:: bash
   
   make install

To verify the installation, do:

.. code-block:: bash

   make verify
