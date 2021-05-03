"""
Quantum node controller interface for simulators.

This module provides the `QNodeController` class which can be used by simulators
as a base class for modeling the quantum node controller.
"""

import abc
import logging
from types import GeneratorType
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Type

from netqasm.backend.executor import Executor
from netqasm.backend.messages import (
    InitNewAppMessage,
    Message,
    MessageType,
    OpenEPRSocketMessage,
    Signal,
    SignalMessage,
    StopAppMessage,
    SubroutineMessage,
)
from netqasm.backend.network_stack import BaseNetworkStack
from netqasm.lang.instr import Flavour
from netqasm.lang.parsing import deserialize
from netqasm.lang.subroutine import Subroutine
from netqasm.logging.glob import get_netqasm_logger


class QNodeController:
    """Class for representing a Quantum Node Controller in a simulation.

    A QNodeController represents a physical quantum node controller that handles
    messages coming from the Host, lets the Executor execute subroutines, and sends
    results back to the Host.
    """

    def __init__(
        self,
        name: str,
        instr_log_dir: Optional[str] = None,
        flavour: Optional[Flavour] = None,
        **kwargs,
    ) -> None:
        """QNodeController constructor.

        :param name: name used for logging purposes
        :param instr_log_dir: directory used to write log files to
        :param flavour: which NetQASM flavour this quantum node controller should
            expect and be able to interpret
        """
        self.name: str = name

        self.flavour: Optional[Flavour] = flavour

        self._executor: Executor = self._get_executor_class(flavour=flavour)(
            name=name,
            instr_log_dir=instr_log_dir,
            **kwargs,
        )

        self._message_handlers: Dict[
            MessageType, Callable
        ] = self._get_message_handlers()

        # Keep track of active apps
        self._active_app_ids: Set[int] = set()

        # Keep track of finished messages
        self._finished_messages: List[bytes] = []

        self._finished: bool = False

        self._logger: logging.Logger = get_netqasm_logger(
            f"{self.__class__.__name__}({self.name})"
        )

    @classmethod
    @abc.abstractmethod
    def _get_executor_class(cls, flavour: Optional[Flavour] = None) -> Type[Executor]:
        pass

    @abc.abstractmethod
    def stop(self) -> None:
        pass

    @property
    def finished(self) -> bool:
        return self._finished

    def handle_netqasm_message(
        self, msg_id: int, msg: Message
    ) -> Generator[Any, None, None]:
        yield from self._handle_message(msg_id=msg_id, msg=msg)

    def _handle_message(self, msg_id: int, msg: Message) -> Generator[Any, None, None]:
        self._logger.info(f"Handle message {msg}")
        output = self._message_handlers[msg.TYPE](msg)
        if isinstance(output, GeneratorType):
            yield from output
        self._mark_message_finished(msg_id=msg_id, msg=msg)
        if self.finished:
            self.stop()

    @property
    def has_active_apps(self) -> bool:
        return len(self._active_app_ids) > 0

    @property
    def network_stack(self) -> Optional[BaseNetworkStack]:
        return self._executor.network_stack

    @network_stack.setter
    def network_stack(self, network_stack: BaseNetworkStack) -> None:
        self._executor.network_stack = network_stack

    def _get_message_handlers(self) -> Dict[MessageType, Callable]:
        return {
            MessageType.SIGNAL: self._handle_signal,
            MessageType.SUBROUTINE: self._handle_subroutine,
            MessageType.INIT_NEW_APP: self._handle_init_new_app,
            MessageType.STOP_APP: self._handle_stop_app,
            MessageType.OPEN_EPR_SOCKET: self._handle_open_epr_socket,
        }

    def add_network_stack(self, network_stack: BaseNetworkStack) -> None:
        self._executor.network_stack = network_stack

    @abc.abstractmethod
    def _mark_message_finished(self, msg_id: int, msg: Message) -> None:
        pass

    def _handle_subroutine(self, msg: SubroutineMessage) -> Generator[Any, None, None]:
        subroutine = deserialize(msg.subroutine, flavour=self.flavour)
        self._logger.debug(
            f"Executing next subroutine " f"from app ID {subroutine.app_id}"
        )
        yield from self._execute_subroutine(subroutine=subroutine)

    def _execute_subroutine(self, subroutine: Subroutine) -> Generator[Any, None, None]:
        yield from self._executor.execute_subroutine(subroutine=subroutine)

    def _handle_init_new_app(self, msg: InitNewAppMessage) -> None:
        app_id = msg.app_id
        self._add_app(app_id=app_id)
        max_qubits = msg.max_qubits
        self._logger.debug(
            f"Allocating a new "
            f"unit module of size {max_qubits} for application with app ID {app_id}.\n"
        )
        self._executor.init_new_application(
            app_id=app_id,
            max_qubits=max_qubits,
        )

    def _add_app(self, app_id: int) -> None:
        self._active_app_ids.add(app_id)

    def _remove_app(self, app_id: int) -> None:
        self._active_app_ids.remove(app_id)

    def _handle_stop_app(self, msg: StopAppMessage) -> Generator[Any, None, None]:
        app_id = msg.app_id
        self._remove_app(app_id=app_id)
        self._logger.debug(f"Stopping application with app ID {app_id}")
        yield from self._executor.stop_application(app_id=app_id)

    def _handle_signal(self, msg: SignalMessage) -> None:
        signal = Signal(msg.signal)
        self._logger.debug(
            f"SubroutineHandler at node {self.name} handles the signal {signal}"
        )
        if signal == Signal.STOP:
            self._logger.debug(f"SubroutineHandler at node {self.name} will stop")
            # Just mark that it will stop, to first send back the reply
            self._finished = True
        else:
            raise ValueError(f"Unkown signal {signal}")

    def _handle_open_epr_socket(
        self, msg: OpenEPRSocketMessage
    ) -> Generator[Any, None, None]:
        yield from self._executor.setup_epr_socket(
            epr_socket_id=msg.epr_socket_id,
            remote_node_id=msg.remote_node_id,
            remote_epr_socket_id=msg.remote_epr_socket_id,
        )
