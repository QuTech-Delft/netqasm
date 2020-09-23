from netqasm.settings import get_simulator, Simulator

simulator = get_simulator()

if simulator == Simulator.NETSQUID:
    from netqasm.sdk.classical_communication import ThreadSocket as Socket
    try:
        from squidasm.sdk import NetSquidConnection as NetQASMConnection
    except ModuleNotFoundError:
        raise ModuleNotFoundError(f"to use {Simulator.NETSQUID.value} as simulator, `squidasm` needs to be installed")
elif simulator == Simulator.SIMULAQRON:
    from simulaqron.sdk.socket import Socket  # type: ignore
    try:
        from simulaqron.sdk.connection import SimulaQronConnection as NetQASMConnection
    except ModuleNotFoundError:
        raise ModuleNotFoundError(f"to use {Simulator.SIMULAQRON.value} as simulator, `simulaqron` needs to be installed")
else:
    raise ValueError(f"Unknown simulator {simulator}")
