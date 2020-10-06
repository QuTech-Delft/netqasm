# CHSH Game
The game is played by two players: Alice and Bob. During the game, they cannot communicate, so they have to agree on a strategy beforehand. Alice gets a random input bit `x` and Bob gets a random input bit `y`. Alice should output a bit `a` and Bob a bit `b`. They win the game if and only if `x * y = a + b (mod 2)`.

Classically, the best strategy Alice and Bob can use gives them a winning probability of 0.75 (e.g. always outputting `a = b = 0`).

By creating an EPR pair between them before the game starts, Alice and Bob can use a strategy that gives them a winning probability of roughly 0.85.

In this example, the EPR pair is created through a repeater (between Alice and Bob). The repeater creates an EPR pair with Alice and then teleports its EPR half to Bob.


## Inputs
* `app_alice`:
  * `x` (int): 0 or 1
* `app_bob`:
  * `y` (int): 0 or 1
* `app_repeater`: null

## Output
* `app_alice`:
  * `a` (int): 0 or 1
* `app_bob`:
  * `b` (int): 0 or 1
* `app_repeater`:
  * `m1` (int): 0 or 1
    teleportation correction
  * `m2` (int): 0 or 1
    teleportation correction

Alice and Bob win the CHSH game if and only if `x * y = a + b (mod 2)`.
