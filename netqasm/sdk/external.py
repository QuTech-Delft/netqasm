"""Imports of concrete (external) implementations of various NetQASM interfaces.

This module re-exports concrete types that are defined externally (e.g. in SquidASM).
The types are re-exported under generic names, such that client code does not need to
use the concrete external names.
Which of the concrete implementations is re-exported depends on global variables (most
importantly the variable indicating which simulator should be used).

For example, an application may import the `NetQASMConnection` name from
`netqasm.sdk.external`, while having set the simulator type to NETSQUID.
This results in the import resolving to an import of
`squidasm.run.multithread.sdk.NetSquidConnection`, even though the application never
had to specify this concrete name. This allows the same application code to be used
with different implementations of `NetQASMConnection`.
"""

from netqasm.runtime.settings import Simulator, get_is_using_hardware, get_simulator

simulator = get_simulator()
is_using_hardware = get_is_using_hardware()

if is_using_hardware:
    try:
        from qnodeos.sdk.connection import (
            QNodeOSConnection as NetQASMConnection,  # type: ignore
        )
        from qnodeos.sdk.socket import Socket  # type: ignore

        from netqasm.runtime.hardware import run_application  # type: ignore
    except ModuleNotFoundError:
        raise ModuleNotFoundError("to use QNodeOS , `qnodeos` needs to be installed")
elif simulator == Simulator.NETSQUID:
    try:
        from squidasm.nqasm.multithread import (
            NetSquidConnection as NetQASMConnection,  # type: ignore
        )
        from squidasm.run.multithread.simulate import (
            simulate_application,  # type: ignore
        )
        from squidasm.util.sim import get_qubit_state  # type: ignore

        from netqasm.sdk.classical_communication import (
            ThreadBroadcastChannel as BroadcastChannel,  # type: ignore
        )
        from netqasm.sdk.classical_communication import (
            ThreadSocket as Socket,  # type: ignore
        )
    except ModuleNotFoundError:
        raise ModuleNotFoundError(
            f"to use {Simulator.NETSQUID.value} as simulator, `squidasm` needs to be installed"
        )
elif simulator == Simulator.NETSQUID_SINGLE_THREAD:
    try:
        from squidasm.nqasm.singlethread.connection import (
            NetSquidConnection as NetQASMConnection,  # type: ignore
        )
        from squidasm.nqasm.singlethread.csocket import (
            NetSquidSocket as Socket,  # type: ignore
        )

        from netqasm.sdk.classical_communication import (
            ThreadBroadcastChannel as BroadcastChannel,  # type: ignore
        )

    except ModuleNotFoundError:
        raise ModuleNotFoundError(
            f"to use {Simulator.NETSQUID.value} as simulator, `squidasm` needs to be installed"
        )
elif simulator == Simulator.SIMULAQRON:
    try:
        from simulaqron.run.run import (
            run_applications as simulate_application,  # type: ignore
        )
        from simulaqron.sdk.broadcast_channel import BroadcastChannel  # type: ignore
        from simulaqron.sdk.connection import (
            SimulaQronConnection as NetQASMConnection,  # type: ignore
        )
        from simulaqron.sdk.socket import Socket  # type: ignore
        from simulaqron.sim_util import get_qubit_state  # type: ignore
    except ModuleNotFoundError:
        raise ModuleNotFoundError(
            f"to use {Simulator.SIMULAQRON.value} as simulator, `simulaqron` needs to be installed"
        )
elif simulator == Simulator.DEBUG:
    from netqasm.runtime.debug import get_qubit_state  # type: ignore
    from netqasm.runtime.debug import run_application  # type: ignore
    from netqasm.sdk.classical_communication import (
        ThreadBroadcastChannel as BroadcastChannel,  # type: ignore
    )
    from netqasm.sdk.classical_communication import (
        ThreadSocket as Socket,  # type: ignore
    )
    from netqasm.sdk.connection import (
        DebugConnection as NetQASMConnection,  # type: ignore
    )
else:
    raise ValueError(f"Unknown simulator {simulator}")
