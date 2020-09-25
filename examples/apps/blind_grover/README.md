# Blind Grover's algorithm

This example demonstrates the blind execution of Grover's algorithm on 2 input qubits. 

The situation is as follows. An oracle takes as input one of 4 possible values (00, 01, 10 or 11) and outputs 1 for one of these (the 'tagged' value), and 0 for the others.
Grover's algorithm describes a quantum circuit that can determine which of the 4 values is 'tagged', while querying the oracle only once.

To blindly execute Grover's algorithm, we need to transform it into a measurement-based quantum computation (MBQC).

First we write the circuit representation of the algorithm in a convenient form:
```c
|+> - . - Rz(pi/2 or -pi/2) - H - . ------------------- measure Y -> result0
      |                           |
|+> - . ------------------------- . - Rz(0 or pi) - H - measure Y -> result1
```
The `pi/2 or -pi/2` and `0 or pi` correspond to the 2 bits describing the oracle. If the 'tagged' value is `x`, the corresponding Z-rotations `phi1` (top qubit) and `phi2` (bottom qubit) should be:

| x     | phi1  | phi2 |
| ------|:-----:| ----:|
| 00    | pi/2  | pi   |
| 01    | pi/2  | 0    |
| 10    | -pi/2 | 0    |
| 11    | -pi/2 | pi   |

To transform the above circuit into a MBQC, we use 4 qubits: `q0`, `q1`, `q2` and `q3`, aligned in a cluster as follows.
```c
q1 -- q0
 |  /
 | /
q2 -- q3
```
We fix `q0` and `q3` to start in the `|+>` state. `q1` and `q2` start as `Rz(theta1) |+>` and `Rz(theta2) |+>` respectively. CPHASE gates are applied between qubits connected in the cluster. 

Measuring `q1` with angle `phi1` and `q2` with angle `phi2` is then equivalent to applying the above circuit on the logical input state `|+>|+>`. The output (before measuring Y) is in qubits `q0` and `q3`.

Alice lets Bob perform this MBQC *blindly* by preparing (using teleportation) qubits `q1` and `q2` with angles `theta1` and `theta2` only known to her. Furthermore, she does not send the measurement angles `phi1` and `phi2` directly, but padded with Pauli-Z operations, depending on her key bits `r1` and `r2`.


## Inputs
* `app_alice`:
  * `b0` (int): first bit of the value that is tagged by the oracle.
  * `b1` (int): second bit of the value that is tagged by the oracle.
  * `r1` (int): key bit used by Alice when sending the measurement angle for qubit `q1`.
  * `r2` (int): key bit used by Alice when sending the measurement angle for qubit `q2`.
  * `theta1` (float): angle that qubit `q1` should be initialized in.
  * `theta2` (float): angle that qubit `q2` should be initialized in.
* `app_bob`: null

## Output
* `app_alice`:
  * `result0` (int): first bit of the result value. Should be equal to `b0`.
  * `result1` (int): second bit of the result value. Should be equal to `b1`.
  * `phi1` (float): target angle to measure `q1` in.
  * `phi2` (float): target angle to measure `q2` in.
  * `delta1` (float): actual angle that `q1` was measured in.
  * `delta2` (float): actual angle that `q2` was measured in.
  * `s1` (int): output of measurement on `q1`.
  * `s2` (int): output of measurement on `q2`.
  * `m` (List[int]): measurement results `m[i]` of teleporting qubit `q[i]` to Bob.
  * `b0` (int): (see input)
  * `b1` (int): (see input)
  * `r1` (int): (see input)
  * `r2` (int): (see input)
  * `theta1` (float): (see input)
  * `theta2` (float): (see input)
* `app_bob`: null
* `backend`: null
