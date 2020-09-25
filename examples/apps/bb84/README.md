# BB84
This code was based on Matthew Skrzypczyk SimulaQron submission and has been modified to work with NetQASM (orignal code can be found here: http://www.simulaqron.org/competition/)
## Inputs
Specification of how many entangled pairs to generate
* `app_alice`:
  * `num_bits` (int)
* `app_bob`: null
  * `num_bits` (int)

## Output
Raw key (random length) and extracted key (one bit)
* `app_alice`:
  * `key` (int)
  * `raw_key` (List[int])
    example: [0, 0, 1, 1]
* `app_bob`:
  * `key` (int)
  * `raw_key` (List[int])
    example: [0, 0, 1, 1]
* `backend`: null
