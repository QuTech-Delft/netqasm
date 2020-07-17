import ctypes

from netqasm.subroutine import Subroutine, Command
from netqasm import encoding
from netqasm.oop.instr import InstrMap

INSTR_ID = ctypes.c_uint8


def serialize_subroutine(subroutine: Subroutine) -> bytes:
    pass

def serialize_command(command: Command) -> bytes:
    pass

class Deserializer:
    def __init__(self, instr_map: InstrMap):
        self.instr_map = instr_map

    def _parse_metadata(self, raw):
        metadata = raw[:encoding.METADATA_BYTES]
        metadata = encoding.Metadata.from_buffer_copy(metadata)
        data = raw[encoding.METADATA_BYTES:]
        return metadata, data

    def deserialize_subroutine(self, raw: bytes) -> Subroutine:
        metadata, raw = self._parse_metadata(raw)
        if (len(raw) % 7) != 0:
            raise ValueError("Length of data not a multiple of command length")
        num_commands = int(len(raw) / 7)
        commands = [
            self.deserialize_command(raw[i * 7:(i + 1) * 7])
            for i in range(num_commands)]
        return Subroutine(
            netqasm_version=tuple(metadata.netqasm_version),
            app_id=metadata.app_id,
            commands=commands,
        )

    def deserialize_command(self, raw: bytes) -> Command:
        # peek next byte to check instruction type
        # print(f"raw command: {raw}")
        # print(f"id map: {self.id_map}")
        instr_id = INSTR_ID.from_buffer_copy(raw[:1]).value
        instr_cls = self.instr_map.id_map[instr_id]
        instr = instr_cls.deserialize_from(raw)
        return instr