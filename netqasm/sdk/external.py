from netqasm.runtime.settings import get_simulator, Simulator, get_is_using_hardware

simulator = get_simulator()
is_using_hardware = get_is_using_hardware()

if is_using_hardware:
    try:
        from qnodeos.sdk.socket import Socket  # type: ignore
        from qnodeos.sdk.connection import QNodeOSConnection as NetQASMConnection  # type: ignore
        from netqasm.runtime.hardware import run_applications  # type: ignore
    except ModuleNotFoundError:
        raise ModuleNotFoundError(
            "to use QNodeOS , `qnodeos` needs to be installed"
        )
elif simulator == Simulator.NETSQUID:
    try:
        from netqasm.sdk.classical_communication import ThreadSocket as Socket  # type: ignore
        from netqasm.sdk.classical_communication import ThreadBroadcastChannel as BroadcastChannel  # type: ignore
        from squidasm.sdk import NetSquidConnection as NetQASMConnection  # type: ignore
        from squidasm.sim_util import get_qubit_state  # type: ignore
        from squidasm.run import run_applications  # type: ignore
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
elif simulator == Simulator.DEBUG:
    from netqasm.sdk.classical_communication import ThreadSocket as Socket  # type: ignore
    from netqasm.sdk.classical_communication import ThreadBroadcastChannel as BroadcastChannel  # type: ignore
    from netqasm.sdk.connection import DebugConnection as NetQASMConnection  # type: ignore
    from netqasm.runtime.debug import get_qubit_state  # type: ignore
    from netqasm.runtime.debug import run_applications  # type: ignore
else:
    raise ValueError(f"Unknown simulator {simulator}")
