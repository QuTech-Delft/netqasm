CHANGELOG
=========

2022-02-25 (0.9.0)
------------------
- Refactored SDK code
- Added `loop_until` context to SDK
- Added `min_fidelity_all_at_end` EPR generation parameter
- Added explicity `create_keep`, `create_measure` and `create_rsp` methods (and similar for `recv_`) to `EPRSocket`.
  The old `create` and `recv` methods are deprecated.
- Added builder tests
- Applied formatting on examples

2021-11-15 (0.8.6)
------------------
- Explicitly use MIT license
- Reformat some imports for better autodocgen

2021-11-08 (0.8.5)
------------------
- Fixed bug in Bloch sphere representation calculation.

2021-09-27 (0.8.4)
------------------
- Updated QKD app config.

2021-09-24 (0.8.3)
------------------
- Added QNE-specific apps to `netqasm/examples/qne_apps`.

2021-09-20 (0.8.2)
------------------
- Small fix in MANIFEST.in file

2021-09-20 (0.8.1)
------------------
- Added MANIFEST.in file

2021-09-19 (0.8.0)
------------------
- Added breakpoint instruction to NetQASM language.
- Re-organized examples.
- Made compatible with SquidASM 0.8.0.

2021-09-10 (0.7.7)
------------------
- Fixed bug where registers were not freed after only being used temporarily.
- Package installation now used `pyproject.toml`.

2021-07-13 (0.7.5)
------------------
- Added support for Remote State Preparation entanglement requests.

2021-06-22 (0.7.4)
------------------
- Fixed bug where Builder's App ID was not updated when Connection's App ID changed.

2021-06-14 (0.7.3)
------------------
- Added `max_time` and `time_unit` parameters to `EPRSocket.create()`
- Added `SubroutineAbortedError` type

2021-05-10 (0.7.2)
------------------
- Temporarily disable `test_create_epr_m.py` test
- Temporarily disable `link_layer_md` example

2021-05-10 (0.7.1)
------------------
- Added docstrings to a large part of the codebase
- Some refactoring based on inconsistencies found while documenting

2021-05-02 (0.7.0)
------------------
- Added type hints to most of the code.
- Now using the `black` and `isort` formatters for the whole repo.
- Extracted pre-subroutine construction out of the Connection class and moved to the Builder class.
- Improved type hints related to numpy types.
- Added convenience methods to the `SharedMemory` class.
- Added support for single-threaded SquidASM simulator.
- Bumped qlink-layer requirement to 1.0.0. Arrays for EPR instructions still use the 0.1.0 format.
- Added a compatibility module for simulators that use qlink-layer 1.0.0 themselves but want to interpret EPR arrays using 0.1.0.
- Updated code that is deprecated in NetSquid 1.0 (it is now compatible with 1.0).

2021-02-05 (0.6.0)
------------------
- Added support for choosing the measurement basis for M-type EPR generation.
- Added the ability to manually create a Register in the SDK. Further use with these Registers is limited for now.
- Added interfaces for applications and the runtime environment, to make it easier to instantiate and run apps.
- Added the `netqasm qne login` and `netqasm qne logout` commands.
- Renamed `Executioner` to `Executor`.
- Optimized initialization of arrays when all elements have the same initial value (use a loop).
- Fixed NV compilation when doing sequential EPR create commands.
- Fixed NV compilation of `K` gates.
- Fixed bug where multiple branch labels with the same name could appear.

2021-02-05 (0.5.3)
------------------
- Reverted patches 0.5.1 and 0.5.2.
  0.5.3 is exactly the same as 0.5.0.

2021-01-21 (0.5.2)
------------------
- Added support for choosing the measurement basis for M-type EPR generation.
- Added the ability to manually create a Register in the SDK. Further use with these Registers is limited for now.
- Added interfaces for applications and the runtime environment, to make it easier to instantiate and run apps.
- Added the `netqasm qne login` and `netqasm qne logout` commands.

2021-01-15 (0.5.1)
------------------
- Renamed `Executioner` to `Executor`.
- Fixed NV compilation when doing sequential EPR create commands.

2020-12-17 (0.5.0)
------------------
- Removed the QST (qubit state) field from log entries.
- The QGR (qubit groups) field now contains a dict of *all* qubit groups in the whole simulation,
  so also of qubits not directly acted on in the current logged operation.
- Added the `StructuredMessage` class in the SDK, which distinguishes between a header and the payload.
- Added `send_structured` and `recv_structured` functions to the `Socket` class for communication `StructuredMessage`s.
- Added `send_silent` and `recv_silent` functions to the `Socket` class for sending standard messages
  that are not logged to the `<role>_class_comm.yaml` files.
- Added `sim_states` module to the SDK with some helper functions for dealing with NetSquid (only works with the `netsquid`
  backend).
- Added the `--log-to-files` CLI parameter. If `True`, no logs are written to any files.
- The `Depolarise` NoiseType for network links now always generates general mixed states, instead of either a perfect 
  state or a fully mixed state.
- Added a `DiscreteDepolarise` NoiseType for network links that has the old behavior of `Depolarise`.
- Log directories and Python cache files are not anymore copied from the `teleport` example when creating using
  `netqasm new` or `netqasm init`.
- `netqasm new` and `netqasm init` now also create a `results_config.json` file.
- Added support for more accurate NV simulation. A `nv.yaml` file can be used additionally to the `network.yaml` file.
- The BB84 example was changed to use Create and Keep entanglement generation.
- Added `results_config.json` to the `bb84` and `teleport` examples.
- Fixed bugs in CLI unit test.
- Fixed a bug related to vritual address allocation.

2020-11-26 (0.4.2)
------------------
- Fixed a bug where the `EPRSocket` would return an incorrect `min_fidelity` value.

2020-11-24 (0.4.1)
------------------
- Added `return_arrays` argument to the `NetQASMConnection` constructor.
  When `False`, no arrays are returned at the end of a subroutine, even if they are used in that subroutine.
- The NV compiler now moves a qubit (if any) from the electron to the carbon before generating another entangled qubit.
- Added a `mov` instruction to the vanilla flavour. For now only used by the NV compiler, and is not in the SDK.

2020-11-20 (0.4.0)
------------------
- Added preliminary documentation, including a quickstart and information about the SDK.
  Build it locally using `make build` from within the `docs` directory.
- Added `netqasm new` and `netqasm init` commands.
- Internal restructuring of modules.
- Logging and configuration formats are now described as dataclasses in `netqasm.runtime.interface`.
- Added more results to the BB84 application output.
- Distinguish between 'Measure Directly' and 'Create and Keep' types of entanglement in the network log.
- Fixes regarding entanglement logging and qubit group calculation.
- Instruction log files now again use the role name instead of the node name.
- Made array IDs, EPR socket IDs and node IDs `int32` instead of `uint32` such that they can be stored in registers.
- Added `min_fidelity` to EPR socket.

2020-10-19 (0.3.0)
------------------
- Added `netqasm run` command to launch applications without also starting a simulation backend.
  It allows the same additional arguments as `netqasm simulate`, except simulation-specifc ones like `--simulator`.
- Added the `RegFuture` class representing values that become available in a register rather than an array.
- Added the `store_array` optional argument to `qubit.measure()`. If False, the result is a `RegFuture`.
- Improved simplification of `(n, d)` values for angles. Both `n` and `d` are now as small as possible.
- When *not* using a simulator backend, the NV compiler now always outputs angle values such that `d = 4`.

2020-10-08 (0.2.0)
------------------
- Example apps have moved into the netqasm module `netqasm/examples/apps`
- Now logging all quantum gates in the instructions log files.
- Remove CREATE_EPR and RECV_EPR from instructions log files.
- Add channels to network log (PTH).
- Log the start of each EPR pair generation in network log file.
- Log qubit IDs in the network log.
- Log both physical and virtual qubit IDs in the instructions log files.
- The names of roles in the examples have been updated.

2020-09-25 (0.1.0)
------------------
- The CLI from `squidasm` is now moved to here and can be called as `netqasm`.
  It works the same as before with the options to the arguments `simulate`.
  Only difference is that it now takes an option `--simulator` which can either be `netsquid` (producing the same behaviour as the previous `squidasm` CLI) or `simulaqron`.
  Note that `squidasm` or `simulaqron` needs to be installed in the respective case.
  The choice of simulator can also be done by setting the environment variable `NETQASM_SIMULATOR`.
- Tests and examples for the SDK have now moved from `squidasm` to here.
  In particular the implemented apps that previously was in `squidasm/examples/apps` can now be found in `netqasm/examples/apps`.
- Code not specific to a simulator, for example a base class for the `SubroutineHandler` and function `simulate_apps` have moved to here to be reused by all simulators.

2020-09-23 (0.0.13)
------------------
- Made a base subroutine handler class.
- Added definition of return messages from qnodeos.

2020-09-23 (0.0.12)
------------------
- Use correct NV gates in when compiling.

2020-09-22 (0.0.11)
------------------
- Now using binary encoding for messages from host to qnodeos.

2020-09-17 (0.0.10)
------------------
- `netqasm` does not depend on `cqc` anymore.

2020-09-09 (0.0.9)
------------------
- Instrs-logging now support qubit IDs and qubit states for all qubits involved in the operation.
- Instrs-logging now support what to specify what qubits have at some point interacted in the simulaton.

2020-08-27 (0.0.8)
------------------
- Moved syntax highlighting files for vim to separate repo.

2020-08-14 (0.0.7)
------------------
- Added static checks with mypy.
- Large refactoring of how instructions are handled internally.
- Add concept of NetQASM flavours and a compiler which uses this.
- Compilation of two-qubit gates for NV.

2020-07-09 (0.0.6)
------------------
- Fixed failing examples and changed default config to only use the dataclass.

2020-07-09 (0.0.5)
------------------
- Fixed bug when logging PRC.
- SDK now supports addition of future.
- Loggers are saved at end of simulation.
- Log host line numbers across multiple files.
- Function in SDK to generate GHZ state.
- Added broadcast-channel to SDK.
- Alignment to QNodeOS.
- Application logger.
- Log if a qubit is entangled.
- Allow for parallel execution of subroutines.

2020-05-20 (0.0.4)
------------------
- Output logs are now in yaml format

2020-05-20 (0.0.3)
------------------
- Fixed bug when checking that num random bases is 2.

2020-05-19 (0.0.2)
------------------
- Create EPR of request M now supported.
- Added EPRSocket class to encapsulate an EPR circuit connection for entanglement generation.
- Added structured logging for classical messages.
- Errors in Executioner now also show which line in subroutine failed.
- Added gate mapping of single-qubit gates to NV.
- State prepation function for single-qubit states.
- Added rotation gates.
- Possibility to specify rotation angle as float which gets converted into sequence of NetQASM rotations.

2020-05-06 (0.0.1)
------------------
- Main changes are the addition of contexts for doing looping, if-statements etc in the SDK.

2020-02-15 (0.0.0)
------------------
- Created this package
