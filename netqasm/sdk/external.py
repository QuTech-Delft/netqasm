from netqasm.settings import get_backend, Backend

backend = get_backend()

if backend == Backend.NETSQUID:
    from netqasm.sdk.classical_communication import ThreadSocket as Socket
    try:
        from squidasm.sdk import NetSquidConnection as NetQASMConnection
    except ModuleNotFoundError:
        raise ModuleNotFoundError(f"to use {Backend.NETSQUID.value} as backend, `squidasm` needs to be installed")
elif backend == Backend.SIMULAQRON:
    from simulaqron.sdk.socket import Socket  # type: ignore
    try:
        from simulaqron.sdk.connection import SimulaQronConnection as NetQASMConnection
    except ModuleNotFoundError:
        raise ModuleNotFoundError(f"to use {Backend.SIMULAQRON.value} as backend, `simulaqron` needs to be installed")
else:
    raise ValueError(f"Unknown backend {backend}")
