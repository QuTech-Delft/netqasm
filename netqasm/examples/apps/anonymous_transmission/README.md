# Anonymous transmission
## Inputs

Specification of who the `sender` and `receiver` is together with what qubit state to teleport.
Each node has the following (optional) input:
* `sender`: (bool)
* `receiver`: (bool)
* `phi` (float)
* `theta` (float)
There should be exactly on `sender` and exactly one `receiver`.

## Output
The state of the teleported qubit at the `receiver`. The rest of the nodes has not output (`null`):
* `qubit_state`: (List[List[complex]])
   example: `[[0.5, -0.5j], [0.5j, 0.5]]`
