"""
NetQASM subroutine definitions.

This module contains the `Subroutine` class which represents a static (not being
executed) NetQASM subroutine.
"""


from __future__ import annotations

from dataclasses import dataclass
from typing import List

from netqasm.lang import encoding
from netqasm.lang.instr import DebugInstruction, NetQASMInstruction
from netqasm.util.string import rspaces


@dataclass
class Subroutine:
    """
    A :class:`~.Subroutine` object represents a subroutine consisting of valid
    instructions, i.e. objects deriving from :class:`~.NetQASMInstruction`.

    :class:`~.Subroutine` s are executed by :class:`~.Executor` s.
    """

    netqasm_version: tuple
    app_id: int
    commands: List[NetQASMInstruction]

    def __str__(self):
        to_return = f"Subroutine (netqasm_version={self.netqasm_version}, app_id={self.app_id}):\n"
        to_return += " LN | HLN | CMD\n"
        for i, command in enumerate(self.commands):
            if isinstance(command, DebugInstruction):
                to_return += f"# {command.text}\n"
            else:
                to_return += f"{rspaces(i)} {command.debug_str}\n"
        return to_return

    def __len__(self):
        return len(self.commands)

    @property
    def cstructs(self):
        metadata = encoding.Metadata(
            netqasm_version=self.netqasm_version,
            app_id=self.app_id,
        )
        return [metadata] + [command.serialize() for command in self.commands]

    def __bytes__(self):
        return b"".join(bytes(cstruct) for cstruct in self.cstructs)
