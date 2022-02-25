# NetQASM (0.9.0)
[![Documentation](https://readthedocs.org/projects/netqasm/badge/?version=latest)](https://netqasm.readthedocs.io/en/latest/?badge=latest)

Utilities for writing, compiling, and running quantum network applications.

## Intro
NetQASM is an instruction set architecture that allows one to interface with quantum network controllers and run applications on a quantum network. Applications may be written directly in the NetQASM language, which resembles assembly code. However, this package also provides an SDK which allows writing application code in Python.
For the paper introducing NetQASM, see [here](https://arxiv.org/abs/2111.09823).

Applications written with this SDK may be run on a simulator backend, like [SquidASM](https://github.com/QuTech-Delft/squidasm) or [SimulaQron](https://github.com/SoftwareQuTech/SimulaQron). In the future, these same applications may be run on a hardware backend consisting of real implementations of quantum network controllers.

This NetQASM Python library is used by the [QNE ADK](https://github.com/QuTech-Delft/qne-adk), which allows interaction with the [Quantum Network Explorer](https://www.quantum-network.com/). When developing applications specifically for the QNE platform, it is recommended to use the [QNE ADK](https://github.com/QuTech-Delft/qne-adk).
For more generic application development, this NetQASM package can be used directly.


## Prerequisites
This package has only been tested on Linux, specifically Ubuntu. On Windows, [WSL](https://docs.microsoft.com/en-us/windows/wsl/) may be used.

## Installation

### From PyPI
NetQASM is available as [a package on PyPI](https://pypi.org/project/netqasm/) and can be installed with
```
pip install netqasm
```

### From source
Clone this repository run the install script:

```
git clone https://github.com/QuTech-Delft/netqasm
cd netqasm
make install
```

To verify the installation:
```sh
make verify
```

## Documentation
The documentation is hosted on [Read the Docs](https://netqasm.readthedocs.io/en/latest/).

The documentation source lives in [the docs directory](./docs).
See the [docs README](./docs/README.md) for information about building and rendering docs.


## Examples
Example applications can be found in `netqasm/examples`.

Applications can be run in two ways:
- From the command line, using `netqasm simulate`. 
  This requires the application code to be organized in a directory with a specific format (see the [Application file structure](https://netqasm.readthedocs.io/en/latest/quickstart/file_structure.html) page in the docs).
- By running a Python script that contains code to start the application.

Examples of applications organized in a directory can be found in `netqasm/examples/apps` and `netqasm/examples/qne_apps`.
They can be run on a simulator using
```sh
netqasm simulate --app-dir netqasm/examples/<app>
```

Examples of Python scripts that can run applications can be found in `netqasm/examples/sdk_scripts`. These files can be run directly using `python <filename>`.

`netqasm/examples/sdk_compilation` contains SDK scripts that use a debug backend. Running these files does not involve an actual simulation of the application code but can be used to see the NetQASM subroutines that are compiled from the Python application code.

For more information, check the [documentation](https://netqasm.readthedocs.io/en/latest/).


## CLI
Once installed, `netqasm` can be used as a command-line interface (CLI) to perform various operations.

See `netqasm --help` and `netqasm <command> --help` for the options.

For example, you can use the `--simulator=<simulator>` to specify which simulator to use.
Currently there is support for:
* [SquidASM](https://github.com/QuTech-Delft/squidasm), which internally uses [NetSquid](https://netsquid.org/)
* [SimulaQron](http://www.simulaqron.org/)

We note that SquidASM is the recommended (and also default) simulator since it is generally faster than SimulaQron and can also simulate noise much more accurately.

## License and patent
A patent application (NL 2029673) has been filed which covers parts of the software in this
repository. We allow for non-commercial and academic use but if you want to
explore a commercial market, please contact us for a license agreement.



## Development
For code formatting, [`black`](https://github.com/psf/black) and [`isort`](https://github.com/PyCQA/isort) are used.
Type hints should be added as much as possible.
Types are checked using [`mypy`](https://github.com/python/mypy).

Before code is pushed, make sure that the `make lint` command succeeds, which runs `black`, `isort`, `flake8` and `mypy`.


# Contributors
In alphabetical order:
- Axel Dahlberg
- Carlo Delle Donne
- Wojciech Kozlowski
- Martijn Papendrecht
- Ingmar te Raa
- Bart van der Vecht (b.vandervecht[at]tudelft.nl)