import ctypes
from typing import Optional

from netqasm.lang import encoding
from netqasm.lang.instr import Flavour, NetQASMInstruction, VanillaFlavour
from netqasm.lang.subroutine import Subroutine

INSTR_ID = ctypes.c_uint8


class Deserializer:
    """
    Deserializes raw bytes into a Subroutine, given a Flavour.
    :class:`~.NetQASMInstructions` are immediately created from the binary encoding.

    (This is in contrast with the parsing.text module, which first converts the input
    to a :class:`~.PreSubroutine`, consisting of :class:`~.subroutine.ICmd` s, before transforming it into
    a :class:`~.Subroutine` containing :class:`~.NetQASMInstruction` s.)
    """

    def __init__(self, flavour: Flavour):
        self.flavour = flavour

    def _parse_metadata(self, raw):
        metadata = raw[: encoding.METADATA_BYTES]
        metadata = encoding.Metadata.from_buffer_copy(metadata)
        data = raw[encoding.METADATA_BYTES :]
        return metadata, data

    def deserialize_subroutine(self, raw: bytes) -> Subroutine:
        metadata, raw = self._parse_metadata(raw)
        if (len(raw) % encoding.COMMAND_BYTES) != 0:
            raise ValueError("Length of data not a multiple of command length")
        num_commands = int(len(raw) / encoding.COMMAND_BYTES)

        commands = [
            self.deserialize_command(
                raw[i * encoding.COMMAND_BYTES : (i + 1) * encoding.COMMAND_BYTES]
            )
            for i in range(num_commands)
        ]

        return Subroutine(
            netqasm_version=tuple(metadata.netqasm_version),
            app_id=metadata.app_id,
            commands=commands,
        )

    def deserialize_command(self, raw: bytes) -> NetQASMInstruction:
        # peek next byte to check instruction type
        id = INSTR_ID.from_buffer_copy(raw[:1]).value

        # use the flavour to check which NetQASMInstruction class should be created
        instr_cls = self.flavour.get_instr_by_id(id)
        instr: NetQASMInstruction = instr_cls.deserialize_from(raw)
        return instr


def deserialize(data: bytes, flavour: Optional[Flavour] = None) -> Subroutine:
    """
    Convert a binary encoding into a Subroutine object.
    The Vanilla flavour is used by default.
    """
    if flavour is None:
        flavour = VanillaFlavour()

    return Deserializer(flavour).deserialize_subroutine(data)
