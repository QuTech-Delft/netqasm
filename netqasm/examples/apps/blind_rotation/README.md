# Blind rotation

This example demonstrates the blind execution of a series of Z-rotations, interspersed with Hadamard gates, on a single qubit.

The *client* Alice first prepares, using teleportation, a series of qubits `q[i]` on the *server* Bob . The state of each qubit `q[i]` is in the XY-plane, with an angle `theta[i]` from the X-axis. The server then applies a controlled-Z (CPHASE) operation on each pair of consecutive qubits. This ends the preparation phase.

The computation now proceeds by Alice sending a series of measurement commands to Bob. For each qubit `q[i]`, Alice's goal is to, on the logical input qubit, perform a Z-rotation of angle `phi[i]`, followed by a Hadamard. She achieves this by asking Bob to measure qubit `q[i]` in a basis spanned by `|0> ± e^{i * delta[i]}|1>`, where `delta[i]` is calculated from `phi[i]`, taking into account the previous measurement outcomes `s` and secret one-time padding `r`.

## Inputs
* `app_alice`:
  * `num_iter` (int): number of times that Alice sends a measurement command to Bob. She will teleport `num_iter + 1` qubits to Bob, of which the last one is not measured, but holds the output state.
  * `theta` (List[float]): holding the angles `theta[i]` for the initial states of qubits `q[i]`. Length of list should be `num_iter + 1`.
  * `phi` (List[float]): target rotations `phi[i]` to be applied (blindly) to qubit `q[i]`. Length of list should be `num_iter`.
  * `r` (List[int]): secret key bits `r[i]`. For each measurement command `i`, Alice adds `r[i] * pi` to the angle for Bob to measure in. Length of list should be `num_iter`.
* `app_bob`:
  * `num_iter` (int): must be the same as Alice's `num_iter`.

## Output
* `app_alice`:
  * `delta` (List[float]): actual angles `delta[i]` that `q[i]` were measured in
  * `s` (List[int]): outputs `s[i]` of measurement on `q[i]`
  * `m` (List[int]): measurement results `m[i]` of teleporting qubit `q[i]` to Bob.
  * `theta` (List[float]): (see input)
  * `phi` (List[float]): (see input)
  * `r` (List[float]): (see input)
* `app_bob`: null
  * `qubit_state` (List[List[complex]]): resulting state in Bob's last qubit (`q[num_iter]`). This state should be (`n = num_iter, + = XOR`):
 ```
Rz(theta[n]) Z^m[n] X^{s[n-1] + r[n-1]} Z^{s[n-2] + r[n-2]} H Rz(phi[n-1]) H Rz(phi[n-2]) ... H Rz(phi[0]) |+>
```
* `backend`: null

