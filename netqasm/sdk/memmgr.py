from __future__ import annotations

from itertools import count
from typing import Dict, List, Set

from netqasm.lang import operand
from netqasm.lang.encoding import REG_INDEX_BITS, RegisterName
from netqasm.lang.parsing.text import parse_register
from netqasm.sdk.futures import Array
from netqasm.sdk.qubit import Qubit


class MemoryManager:
    def __init__(self) -> None:
        # All qubits active for this connection
        self._active_qubits: List[Qubit] = []

        # Registers for looping etc.
        # These are registers that are for example currently hold data and should
        # not be used for something else.
        # For example a register used for looping.
        self._active_registers: Set[operand.Register] = set()

        self._used_meas_registers: Dict[operand.Register, bool] = {
            operand.Register(RegisterName.M, i): False for i in range(16)
        }

        # Registers to return
        self._registers_to_return: List[operand.Register] = []

        self._used_array_addresses: List[int] = []

        # Arrays to return
        self._arrays_to_return: List[Array] = []

    def inactivate_qubits(self) -> None:
        while len(self._active_qubits) > 0:
            q = self._active_qubits.pop()
            q.active = False

    def get_active_qubits(self) -> List[Qubit]:
        return self._active_qubits

    def is_qubit_active(self, q: Qubit) -> bool:
        return q in self._active_qubits

    def activate_qubit(self, q: Qubit) -> None:
        self._active_qubits.append(q)

    def deactivate_qubit(self, q: Qubit) -> None:
        self._active_qubits.remove(q)

    def get_new_qubit_address(self) -> int:
        qubit_addresses_in_use = [q.qubit_id for q in self._active_qubits]
        for address in count(0):
            if address not in qubit_addresses_in_use:
                return address
        raise RuntimeError("Could not get new qubit address")

    def is_reg_active(self, reg: operand.Register) -> bool:
        return reg in self._active_registers

    def add_active_reg(self, reg: operand.Register) -> None:
        if reg in self._active_registers:
            raise ValueError(f"Register {reg} is already active")
        self._active_registers.add(reg)

    def remove_active_reg(self, reg: operand.Register) -> None:
        self._active_registers.remove(reg)

    def meas_reg_set_used(self, reg: operand.Register) -> None:
        self._used_meas_registers[reg] = True

    def meas_reg_set_unused(self, reg: operand.Register) -> None:
        self._used_meas_registers[reg] = False

    def get_new_meas_outcome_reg(self) -> operand.Register:
        # Find the next unused M-register.
        for reg, used in self._used_meas_registers.items():
            if not used:
                self._used_meas_registers[reg] = True
                return reg
        raise RuntimeError("Ran out of M-registers")

    def reset_used_meas_registers(self) -> None:
        self._used_meas_registers = {
            operand.Register(RegisterName.M, i): False for i in range(16)
        }

    def add_reg_to_return(self, reg: operand.Register) -> None:
        self._registers_to_return.append(reg)

    def get_registers_to_return(self) -> List[operand.Register]:
        return self._registers_to_return

    def reset_registers_to_return(self) -> None:
        self._registers_to_return = []

    def get_inactive_register(self, activate: bool = False) -> operand.Register:
        for i in range(2 ** REG_INDEX_BITS):
            register = parse_register(f"R{i}")
            if not self.is_reg_active(register):
                if activate:
                    self.add_active_reg(register)
                return register
        raise RuntimeError("could not find an available loop register")

    def get_new_array_address(self) -> int:
        if len(self._used_array_addresses) > 0:
            # last element is always the highest address
            address = self._used_array_addresses[-1] + 1
        else:
            address = 0
        self._used_array_addresses.append(address)
        return address

    def add_array_to_return(self, array: Array) -> None:
        self._arrays_to_return.append(array)

    def get_arrays_to_return(self) -> List[Array]:
        return self._arrays_to_return

    def reset_arrays_to_return(self) -> None:
        self._arrays_to_return = []

    def reset(self) -> None:
        self.reset_arrays_to_return()
        self.reset_registers_to_return()
        self.reset_used_meas_registers()
