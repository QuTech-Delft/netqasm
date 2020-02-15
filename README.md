NetQASM (0.0.0)
=====================================================

Welcome to NetQASM's README.

To install the package do:
```bash
make install
```

To verify the installation do:
```
make verify
```

Examples
--------

To run a file (`examples/netqasm_files/simple_measure.nqasm`) containing the script:
```
# NETQASM 1.0
# APPID 0
# DEFINE op h
# DEFINE q @0
creg(1) m
qreg(1) q!
init q!
op! q! // this is a comment
meas q! m
output m
beq m[0] 0 EXIT
x q!
EXIT:
// this is also a comment
```
which can be found [here](https://gitlab.tudelft.nl/qinc-wehner/NetQASM/NetQASM/blob/master/examples/netqasm_files/simple_measure.nqasm), run the following:
```sh
netqasm execute simple_measure.nqasm
```
the output can be then be found in the file `simple_measure.out` as triggered by the line `output m` which outputs the register `m`.

Note that to actually perform quantum operations on simulated qubits you will need for example `squidasm`.
