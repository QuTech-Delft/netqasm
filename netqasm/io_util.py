import os

from netqasm.parsing import parse_text_subroutine
from netqasm.executioner import Executioner
from netqasm.logging import set_log_level
try:
    from squidasm.qnodeos import SubroutineHandler
    from squidasm.network_setup import get_node
    from squidasm.messages import Message, MessageType, InitNewAppMessage
    from squidasm.queues import Signal
    import netsquid as ns
except ModuleNotFoundError:
    SubroutineHandler = None


NETQASM_EXT = ".nqasm"


def _read_netqasm_file(netqasm_file):
    if not netqasm_file.endswith(NETQASM_EXT):
        raise ValueError("{netqasm_file} is not a NetQASM file, should have '{NETQASM_EXT}' extension")
    with open(netqasm_file, 'r') as f:
        subroutine = f.read()
    subroutine = parse_text_subroutine(subroutine)
    return subroutine


def execute_subroutine(backend, num_qubits, netqasm_file, output_file=None, log_level="WARNING"):
    set_log_level(log_level)
    subroutine = _read_netqasm_file(netqasm_file)
    if backend == "debug":
        shared_memory = _execute_using_debug(
            num_qubits=num_qubits,
            subroutine=subroutine,
        )
    elif backend == "netsquid":
        shared_memory = _execute_using_netsquid(
            num_qubits=num_qubits,
            subroutine=subroutine,
        )
    else:
        raise ValueError("Unkown executioner {executioner}")

    output_data = shared_memory._get_active_values()

    if output_file is None:
        output_file = os.path.splitext(netqasm_file)[0] + ".out"
    with open(output_file, 'w') as f:
        for position, value in output_data:
            f.write(f"{position}: {value}\n")


def _execute_using_debug(num_qubits, subroutine):
    executioner = Executioner()
    # Consume the generator
    list(executioner.init_new_application(app_id=subroutine.app_id, max_qubits=num_qubits))
    executioner._consume_execute_subroutine(subroutine)
    shared_memory = executioner._shared_memories[subroutine.app_id]
    return shared_memory


def _execute_using_netsquid(num_qubits, subroutine):
    if SubroutineHandler is None:
        raise ModuleNotFoundError("To execute a subroutine using NetSquid the package "
                                  "'squidasm' needs to be installed")
    node = get_node(name="node")
    # Create subroutine handler
    subroutine_handler = SubroutineHandler(node=node)
    # Init application
    subroutine_handler._message_queue.put(Message(
        type=MessageType.INIT_NEW_APP,
        msg=InitNewAppMessage(
            app_id=0,
            max_qubits=num_qubits,
            circuit_rules=None,
        )
    ))
    # Send subroutine
    subroutine_handler._message_queue.put(Message(
        type=MessageType.SUBROUTINE,
        msg=bytes(subroutine),
    ))
    # Stop application
    subroutine_handler._message_queue.put(Message(
        type=MessageType.SIGNAL,
        msg=Signal.STOP,
    ))

    subroutine_handler.start()
    ns.sim_run()

    shared_memory = subroutine_handler._executioner._shared_memories[subroutine.app_id]
    return shared_memory
