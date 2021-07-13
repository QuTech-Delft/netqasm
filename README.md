# NetQASM (0.7.5)
Utilities for writing, compiling, and running quantum network applications.

## Intro
NetQASM is an instruction set architecture that allows one to interface with quantum network controllers and run applications on a quantum network.

Applications may be written directly in the NetQASM language, which resembles assembly code. However, this package also provides an SDK which allows writing application code in Python.

Applications written with this SDK may be run on a simulator backend, like `squidasm`,
or on a hardware backend consisting of real implementations of quantum network controllers, like QNodeOS.


## Installation

To install the package:
```sh
make install
```

To verify the installation:
```sh
make verify
```

## Documentation
See the [docs README](./docs/README.md) for information about building and rendering docs.



## Examples
Example applications can be found in `netqasm/examples`.

Applications can be run in two ways:
- From the command line, using `netqasm simulate`. 
  This requires the application code to be organized in a directory with a specific format (see the `Application file structure` page in the docs).
- By running a Python script that contains code to start the application.

Examples of applications organized in a directory can be found in `netqasm/examples/apps`.
They can be run on a simulator using
```sh
netqasm simulate --app-dir netqasm/examples/<app>
```

Examples of Python scripts that can run applications can be found in `netqasm/examples/sdk_examples`. These files can be run directly using `python <filename>`.

For more information, check the [documentation](#documentation).


## CLI
Once installed, `netqasm` can be used as a command-line interface (CLI) to perform various operations.

See `netqasm --help` and `netqasm <command> --help` for the options.

For example you can use the `--simulator=<simulator>` to specify the simulator.
Currently support for:
* [`netsquid`](https://netsquid.org/)
* [`simulaqron`](http://www.simulaqron.org/)


## Syntax
There is a syntax file for vim in [`syntax/vim/nqasm.vim`](https://gitlab.tudelft.nl/qinc-wehner/NetQASM/NetQASM/blob/master/syntax/vim/nqasm.vim) to highlight NetQASM.


## Architecture
See [the architecture document](./netqasm/ARCH.md).


## Development

For code formatting, `black` and `isort` are used.
Type hints should be added as much as possible.
Types are checked using `mypy`.

Before code is merged, make sure that the `make lint` command succeeds, which runs `black`, `isort`, `flake8` and `mypy`.


# Contributors
In alphabetical order:
- Axel Dahlberg
- Martijn Papendrecht
- Bart van der Vecht (b.vandervecht[at]tudelft.nl)