Code and data used for the evaluation section of the [NetQASM paper](https://arxiv.org/abs/2111.09823).

To run the code, [`netqasm`](https://github.com/QuTech-Delft/netqasm) and [`squidasm`](https://github.com/QuTech-Delft/squidasm) need to be installed.

## Producing simulation data and plots

Teleportation fidelity as a function of gate noise (Figure 11.a):
```
$ python netqasm_sim/simulate_teleport.py sweep --param gate_noise --config teleport_cfg1 --num <NUM_ITERATIONS>
$ python netqasm_sim/plot_teleport.py --param gate_noise
```


Teleportation fidelity as a function of gate duration (Figure 11.b):
```
$  python netqasm_sim/simulate_teleport.py sweep --param gate_time --config teleport_cfg1 --num <NUM_ITERATIONS>
$  python netqasm_sim/plot_teleport.py --param gate_time
```


BQC error rate as a function of gate noise (Figure 13):
```
$  python netqasm_sim/simulate_bqc.py sweep --param gate_noise_trap --config near_perfect_nv --num <NUM_ITERATIONS>
$  python netqasm_sim/plot_bqc.py --param gate_noise_trap
```

The simulation data that was used to create the plots in the paper is in the `final_data` directory.