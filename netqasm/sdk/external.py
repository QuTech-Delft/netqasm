from netqasm.settings import get_simulator, Simulator

simulator = get_simulator()

if simulator == Simulator.NETSQUID:
    try:
        from netqasm.sdk.classical_communication import ThreadSocket as Socket
        from netqasm.sdk.classical_communication import ThreadBroadcastChannel as BroadcastChannel
        from squidasm.sdk import NetSquidConnection as NetQASMConnection
        from squidasm.sim_util import get_qubit_state
        from squidasm.run import run_applications
    except ModuleNotFoundError:
        raise ModuleNotFoundError(f"to use {Simulator.NETSQUID.value} as simulator, `squidasm` needs to be installed")
elif simulator == Simulator.SIMULAQRON:
    try:
        from simulaqron.sdk.socket import Socket  # type: ignore
        from simulaqron.sdk.broadcast_channel import BroadcastChannel  # type: ignore
        from simulaqron.sdk.connection import SimulaQronConnection as NetQASMConnection  # type: ignore
        from simulaqron.sim_util import get_qubit_state  # type: ignore
        from simulaqron.run import run_applications  # type: ignore
    except ModuleNotFoundError:
        raise ModuleNotFoundError(
            f"to use {Simulator.SIMULAQRON.value} as simulator, `simulaqron` needs to be installed"
        )
else:
    raise ValueError(f"Unknown simulator {simulator}")
