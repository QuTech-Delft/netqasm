from __future__ import annotations

from itertools import count
from typing import Dict, List, Set

from netqasm.lang import operand
from netqasm.lang.encoding import REG_INDEX_BITS, RegisterName
from netqasm.lang.parsing.text import parse_register
from netqasm.sdk.futures import Array
from netqasm.sdk.qubit import Qubit


class MemoryManager:
    """Container for managing application memory during building.

    Used by a Builder to store information about which registers, arrays,
    and qubits have been allocated, and to (de)allocate these memory locations
    when needed.
    """

    def __init__(self) -> None:
        # All qubits active for this connection
        self._active_qubits: List[Qubit] = []

        # Registers that are in use for holding classical data.
        self._active_registers: Set[operand.Register] = set()

        # Register in use for holding measurement outcomes.
        self._used_meas_registers: Dict[operand.Register, bool] = {
            operand.Register(RegisterName.M, i): False for i in range(16)
        }

        # Registers that need to be returned at the end of the subroutine.
        self._registers_to_return: List[operand.Register] = []

        # Addresses that are already used for allocated arrays.
        self._used_array_addresses: List[int] = []

        # Arrays that need to be returned at the end of the subroutine.
        self._arrays_to_return: List[Array] = []

    def inactivate_qubits(self) -> None:
        """Mark all registers as inactive (i.e. not in use)."""
        while len(self._active_qubits) > 0:
            q = self._active_qubits.pop()
            q.active = False

    def get_active_qubits(self) -> List[Qubit]:
        """Get all qubit locations that are in use."""
        return self._active_qubits

    def is_qubit_active(self, q: Qubit) -> bool:
        """Check if a qubit location is in use."""
        return q in self._active_qubits

    def is_qubit_id_used(self, id: int) -> bool:
        """Check if a qubit ID is in use."""
        return any(q.qubit_id == id for q in self._active_qubits)

    def activate_qubit(self, q: Qubit) -> None:
        """Mark a qubit location as 'in use'."""
        self._active_qubits.append(q)

    def deactivate_qubit(self, q: Qubit) -> None:
        """Mark a qubit location as 'not in use'."""
        self._active_qubits.remove(q)

    def get_new_qubit_address(self) -> int:
        """Get an unused qubit location."""
        qubit_addresses_in_use = [q.qubit_id for q in self._active_qubits]
        for address in count(0):
            if address not in qubit_addresses_in_use:
                return address
        raise RuntimeError("Could not get new qubit address")

    def is_register_active(self, reg: operand.Register) -> bool:
        """Check if a register is in use."""
        return reg in self._active_registers

    def add_active_register(self, reg: operand.Register) -> None:
        """Mark a register as 'in use'."""
        if reg in self._active_registers:
            raise ValueError(f"Register {reg} is already active")
        self._active_registers.add(reg)

    def remove_active_register(self, reg: operand.Register) -> None:
        """Mark a register as 'not in use'."""
        self._active_registers.remove(reg)

    def meas_register_set_used(self, reg: operand.Register) -> None:
        """Mark a measurement register as 'in use'."""
        self._used_meas_registers[reg] = True

    def meas_register_set_unused(self, reg: operand.Register) -> None:
        """Mark a measurement register as 'not in use'."""
        self._used_meas_registers[reg] = False

    def get_new_meas_outcome_register(self) -> operand.Register:
        """Get an un-used measurement register."""
        # Find the next unused M-register.
        for reg, used in self._used_meas_registers.items():
            if not used:
                self._used_meas_registers[reg] = True
                return reg
        raise RuntimeError("Ran out of M-registers")

    def reset_used_meas_registers(self) -> None:
        """Mark all measurement registers as 'not in use'."""
        self._used_meas_registers = {
            operand.Register(RegisterName.M, i): False for i in range(16)
        }

    def add_register_to_return(self, reg: operand.Register) -> None:
        """Let a register be returned at the end of the subroutine."""
        self._registers_to_return.append(reg)

    def get_registers_to_return(self) -> List[operand.Register]:
        """Get all register that are returned at the end of the subroutine."""
        return self._registers_to_return

    def reset_registers_to_return(self) -> None:
        """Clear list of registers that are returned at the end of the subroutine."""
        self._registers_to_return = []

    def get_inactive_register(self, activate: bool = False) -> operand.Register:
        """Get an un-used register."""
        for i in range(2 ** REG_INDEX_BITS):
            register = parse_register(f"R{i}")
            if not self.is_register_active(register):
                if activate:
                    self.add_active_register(register)
                return register
        raise RuntimeError("could not find an available loop register")

    def get_new_array_address(self) -> int:
        """Get an un-used array address."""
        if len(self._used_array_addresses) > 0:
            # last element is always the highest address
            address = self._used_array_addresses[-1] + 1
        else:
            address = 0
        self._used_array_addresses.append(address)
        return address

    def add_array_to_return(self, array: Array) -> None:
        """Let an array be returned at the end of the subroutine."""
        self._arrays_to_return.append(array)

    def get_arrays_to_return(self) -> List[Array]:
        """Get all arrays that are returned at the end of the subroutine."""
        return self._arrays_to_return

    def reset_arrays_to_return(self) -> None:
        """Clear list of arrays that are returned at the end of the subroutine."""
        self._arrays_to_return = []

    def reset(self) -> None:
        """Reset the state of the MemoryManager."""
        self.reset_arrays_to_return()
        self.reset_registers_to_return()
        self.reset_used_meas_registers()
