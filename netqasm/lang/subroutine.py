"""
NetQASM subroutine definitions.

This module contains the `Subroutine` class which represents a static (not being
executed) NetQASM subroutine.
"""


from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

from netqasm.lang import encoding
from netqasm.lang.instr import DebugInstruction, NetQASMInstruction
from netqasm.lang.operand import Operand, Template
from netqasm.lang.version import NETQASM_VERSION
from netqasm.util.string import rspaces


class Subroutine:
    """
    A `Subroutine` object represents a subroutine consisting of valid
    instructions, i.e. objects deriving from `NetQASMInstruction`.

    Subroutines can optionally have *arguments*, which are yet-to-be-defined
    variables that are used in one or more of the instructions in the
    Subroutine. So, a Subroutine can be seen as a function which takes certain
    parameters (arguments). Concrete values for arguments can be given by
    instantiating (using the `instantiate` method).

    `Subroutine`s are executed by `Executor`s.
    """

    def __init__(
        self,
        instructions: Optional[List[NetQASMInstruction]] = None,
        arguments: Optional[List[str]] = None,
        netqasm_version: Tuple[int, int] = NETQASM_VERSION,
        app_id: Optional[int] = None,
    ) -> None:
        self._netqasm_version: Tuple[int, int] = netqasm_version
        self._app_id: Optional[int] = app_id

        self._instructions: List[NetQASMInstruction] = []
        if instructions is not None:
            self.instructions = instructions

        self._arguments: List[str] = []
        if arguments is not None:
            self._arguments = arguments
        else:
            # figure out argument by inspecting all commands
            for instr in self.instructions:
                for op in instr.operands:
                    if isinstance(op, Template):
                        self._arguments.append(op.name)

    @property
    def netqasm_version(self) -> Tuple[int, int]:
        return self._netqasm_version

    @property
    def app_id(self) -> Optional[int]:
        return self._app_id

    @app_id.setter
    def app_id(self, new_app_id: int) -> None:
        self._app_id = new_app_id

    @property
    def instructions(self) -> List[NetQASMInstruction]:
        return self._instructions

    @instructions.setter
    def instructions(self, new_instructions: List[NetQASMInstruction]) -> None:
        self._instructions = new_instructions

    @property
    def arguments(self) -> List[str]:
        return self._arguments

    def instantiate(
        self, app_id: int, arguments: Optional[Dict[str, int]] = None
    ) -> None:
        instrs: List[NetQASMInstruction] = []
        for instr in self.instructions:
            ops: List[Union[Operand, int]] = []
            for op in instr.operands:
                if isinstance(op, Template):
                    assert arguments is not None
                    ops.append(arguments[op.name])
                else:
                    ops.append(op)
            instrs.append(instr.from_operands(ops))

        self.instructions = instrs
        self._app_id = app_id

    def __str__(self):
        result = "Subroutine"
        if len(self.arguments) > 0:
            result += "(" + ",".join(arg_name for arg_name in self.arguments) + ")"
        result += "\n"
        result += f"NetQASM version: {self.netqasm_version}\n"
        result += f"App ID: {self.app_id}\n"

        result += " LN | HLN | CMD\n"
        for i, instr in enumerate(self.instructions):
            if isinstance(instr, DebugInstruction):
                result += f"# {instr.text}\n"
            else:
                result += f"{rspaces(i)} {instr.debug_str}\n"
        return result

    def __len__(self):
        return len(self.instructions)

    @property
    def cstructs(self):
        assert self.app_id is not None

        metadata = encoding.Metadata(
            netqasm_version=self.netqasm_version,
            app_id=self.app_id,
        )
        return [metadata] + [instr.serialize() for instr in self.instructions]

    def __bytes__(self):
        return b"".join(bytes(cstruct) for cstruct in self.cstructs)
