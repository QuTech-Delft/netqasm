# Magic square
## Inputs
Specification of what `row` to bob and what `col` to alice.
`strategy` for both nodes for what measurements to apply.
* `app_alice`:
  * `row` (int)
  * `strategy` (List[List[str]])
    example: `[['XI', 'XX', 'IX'], ['-XZ', 'YY', '-ZX'], ['IZ', 'ZZ', 'ZI']]`
* `app_bob`:
  * `col` (int)
  * `strategy` (List[List[str]])
    example: `[['XI', '-XZ', 'IZ'], ['XX', 'YY', 'ZZ'], ['IX', '-ZX', 'ZI']]`

## Output
`row` and `col` outputed by alice and bob
* `app_alice`:
  * `row` (List[int])
    example: `[1, 1, 0]`
* `app_bob`:
  * `col` (List[int])
    example: `[1, 1, 1]`
* `backend`: null
