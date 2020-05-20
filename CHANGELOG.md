CHANGELOG
=========

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
