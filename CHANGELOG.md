CHANGELOG
=========

Upcoming
--------

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
