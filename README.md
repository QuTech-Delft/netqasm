# NetQASM (0.7.0)
Utilities for writing, compiling, and running quantum network applications.

## Intro
NetQASM is an instruction set architecture that allows one to control quantum network controllers and run applications on a quantum network.

Applications may be written directly in the NetQASM language, which resembles assembly code. However, this repository provides an SDK which allows writing application code in Python.


## Installation

To install the package:
```sh
make install
```

To verify the installation:
```sh
make verify
```



## Examples
Example applications can be found in `netqasm/examples`.

Applications can be run in two ways:
- From the command line, using `netqasm simulate`. 
  This requires the application code to be organized in a directory with a specific format (see below).
- By running a Python script that contains code to start the application.

Examples of applications organized in a directory can be found in `netqasm/examples/apps`.
They can be run on a simulator using
```sh
netqasm simulate --app-dir netqasm/examples/<app>
```

Examples of Python scripts that can run applications can be found in `netqasm/examples/sdk_examples`. These files can be run directly using `python <filename>`.

## CLI
Once installed, `netqasm` can be used as a command-line interface (CLI) to perform various operations.

See `netqasm --help` and `netqasm <command> --help` for the options.

For example you can use the `--simulator=<simulator>` to specify the simulator.
Currently support for:
* [`netsquid`](https://netsquid.org/)
* [`simulaqron`](http://www.simulaqron.org/)


### Configuration
The applications can be configured by yaml-files in the same folder (e.g. `alice.yaml`) which provides arguments to the application, such as how to initialize the state to be teleported.

Furthermore, the underlying simulated physical quantum network can be configured by the yaml-file `network.yaml`, to provide details of quantum operations, their noise and execution time.

### Logging
In the folder `log` of the application folder records of all runs are stored in folders based on the time it was executed.
There is also a folder `LAST` with the latest log-folder for convinience.
A log-folder contains a seperate log-file for each host from the simulation (e.g. `alice.log`).

A line in a log-file looks for example as follows:
```sh
NetQASM.Instr-by-NetSquidExecutor(alice) : WCT=2020-04-23 12:45:10,482 : NST=13952.0 : SID=0 : PRC=18 : HLN=19 : INS=init : Doing instruction init with operands Q0
```
containing the following fields:
> TODO update fields.
* `WCT` (wall-clock time): Timestamp of computer running the simulation.
* `SIT` (simulated time): Timestamp of simulation time (nano-seconds), if supported.
* `SID` (subroutine ID): ID of the subroutine (incemental for subroutines sent by app).
* `PRC` (program counter): Which line/instruction this is in the subroutine.
* `HLN` (host line-number): Which line in the host application (e.g. `app_alice.py`) this instrution corresponds to.
* `INS` (instruction): Which instruction it is.

In the log-folder, there are also files containing information about the NETQASM subroutines sent from the host to the backend in the files called for example `subroutines_alice.pkl`.
These files are pickled version of a list of subroutines (which are dataclasses).

# Syntax
There is a syntax file for vim in [`syntax/vim/nqasm.vim`](https://gitlab.tudelft.nl/qinc-wehner/NetQASM/NetQASM/blob/master/syntax/vim/nqasm.vim) to highlight NetQASM.


## Architecture
See [the architecture document](./netqasm/ARCH.md).


# Development

For code formatting, `black` and `isort` are used.
Type hints should be added as much as possible.
Types are checked using `mypy`.