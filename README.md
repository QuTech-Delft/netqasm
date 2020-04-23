NetQASM (0.0.0)
=====================================================

Welcome to NetQASM's README.

To install the package do:
```sh
make install
```

To verify the installation do:
```sh
make verify
```

Examples
--------
To run a file (`examples/netqasm_files/simple_measure.nqasm`) containing the script:
```
# NETQASM 0.0
# APPID 0
# DEFINE op h
set Q0 0
qalloc Q0
init Q0
op! Q0 // this is a comment
meas Q0 M0
beq M0 0 EXIT
x Q0
EXIT:
ret_reg M0
// this is also a comment
```
which can be found [here](https://gitlab.tudelft.nl/qinc-wehner/NetQASM/NetQASM/blob/master/examples/netqasm_files/simple_measure.nqasm), run the following:
```sh
netqasm execute path/to/folder/simple_measure.nqasm
```
the output can be then be found in the file `simple_measure.out` containing all data returned by running the subroutine (as for example the register returned by the line `ret_reg M0` which outputs the register `M0`).

By setting the option `-b/--backend` you can choose which backend to use to execute the subroutine (currently `debug` or `netsquid`). To use the `netsquid` backend you need `squidasm` installed. The `default` backend performs all classical operations but not the quantum ones (measurement always gives 0).

You can also set for example the loging level with `--log-level` for example (`DEBUG`).

For more options and their description do
```sh
netqasm execute --help
```

Syntax
------
There is a syntax file for vim in [`syntax/vim/nqasm.vim`](https://gitlab.tudelft.nl/qinc-wehner/NetQASM/NetQASM/blob/master/syntax/vim/nqasm.vim) to highlight NetQASM.
