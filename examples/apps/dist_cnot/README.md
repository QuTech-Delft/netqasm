# Teleportation
Performs a CNOT operation distributed over two nodes: Alice and Bob.
Alice owns the control qubit and Bob the target qubit.

## Inputs
Alice: specification of the control qubit
* `app_alice`:
  * `phi` (float)
  * `theta` (float)

Bob: specification of the target qubit
* `app_bob`: 
  * `phi` (float)
  * `theta` (float)

## Output
Measurement results of Alice and Bob's EPR qubits, sent to each other.
* `app_alice`: 
  * `epr_meas` (int): Result of Alice's measurement of her EPR qubit
  * `final_state` (List[List[complex]]): density matrix of the combined control-target state after the distributed CNOT
* `app_bob`: 
  * `epr_meas` (int): Result of Bob's measurement of his EPR qubit
* `backend`: