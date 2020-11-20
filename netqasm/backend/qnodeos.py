import abc
from types import GeneratorType

from netqasm.lang.parsing import deserialize
from netqasm.logging.glob import get_netqasm_logger
from netqasm.backend.messages import MessageType, Signal


class BaseSubroutineHandler:
    def __init__(self, name, instr_log_dir=None, flavour=None, **kwargs):
        """An extremely simplified version of QNodeOS for handling NetQASM subroutines"""
        self.name = name

        self.flavour = flavour

        self._executioner = self._get_executioner_class(flavour=flavour)(
            name=name,
            instr_log_dir=instr_log_dir,
            **kwargs,
        )

        self._message_handlers = self._get_message_handlers()

        # Keep track of active apps
        self._active_app_ids = set()

        # Keep track of finished messages
        self._finished_messages = []

        self._finished = False

        self._logger = get_netqasm_logger(f"{self.__class__.__name__}({self.name})")

    @classmethod
    @abc.abstractmethod
    def _get_executioner_class(cls, flavour=None):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    @property
    def finished(self):
        return self._finished

    def handle_netqasm_message(self, msg_id, msg):
        yield from self._handle_message(msg_id=msg_id, msg=msg)

    def _handle_message(self, msg_id, msg):
        self._logger.info(f'Handle message {msg}')
        output = self._message_handlers[msg.TYPE](msg)
        if isinstance(output, GeneratorType):
            yield from output
        self._mark_message_finished(msg_id=msg_id, msg=msg)
        if self.finished:
            self.stop()

    @property
    def has_active_apps(self):
        return len(self._active_app_ids) > 0

    @property
    def network_stack(self):
        return self._executioner.network_stack

    @network_stack.setter
    def network_stack(self, network_stack):
        self._executioner.network_stack = network_stack

    def _get_message_handlers(self):
        return {
            MessageType.SIGNAL: self._handle_signal,
            MessageType.SUBROUTINE: self._handle_subroutine,
            MessageType.INIT_NEW_APP: self._handle_init_new_app,
            MessageType.STOP_APP: self._handle_stop_app,
            MessageType.OPEN_EPR_SOCKET: self._handle_open_epr_socket,
        }

    def add_network_stack(self, network_stack):
        self._executioner.network_stack = network_stack

    @abc.abstractmethod
    def _mark_message_finished(self, msg_id, msg):
        pass

    def _handle_subroutine(self, msg):
        subroutine = deserialize(msg.subroutine, flavour=self.flavour)
        self._logger.debug(f"Executing next subroutine "
                           f"from app ID {subroutine.app_id}")
        yield from self._execute_subroutine(subroutine=subroutine)

    def _execute_subroutine(self, subroutine):
        yield from self._executioner.execute_subroutine(subroutine=subroutine)

    def _handle_init_new_app(self, msg):
        app_id = msg.app_id
        self._add_app(app_id=app_id)
        max_qubits = msg.max_qubits
        self._logger.debug(f"Allocating a new "
                           f"unit module of size {max_qubits} for application with app ID {app_id}.\n")
        self._executioner.init_new_application(
            app_id=app_id,
            max_qubits=max_qubits,
        )

    def _add_app(self, app_id):
        self._active_app_ids.add(app_id)

    def _remove_app(self, app_id):
        self._active_app_ids.remove(app_id)

    def _handle_stop_app(self, msg):
        app_id = msg.app_id
        self._remove_app(app_id=app_id)
        self._logger.debug(f"Stopping application with app ID {app_id}")
        yield from self._executioner.stop_application(app_id=app_id)

    def _handle_signal(self, msg):
        signal = Signal(msg.signal)
        self._logger.debug(f"SubroutineHandler at node {self.name} handles the signal {signal}")
        if signal == Signal.STOP:
            self._logger.debug(f"SubroutineHandler at node {self.name} will stop")
            # Just mark that it will stop, to first send back the reply
            self._finished = True
        else:
            raise ValueError(f"Unkown signal {signal}")

    def _handle_open_epr_socket(self, msg):
        yield from self._executioner.setup_epr_socket(
            epr_socket_id=msg.epr_socket_id,
            remote_node_id=msg.remote_node_id,
            remote_epr_socket_id=msg.remote_epr_socket_id,
        )
