from __future__ import annotations
import io, struct

class Mp4Box:
    def __init__(self, typ: bytes, size: int, start_off: int):
        self.type = typ
        self.size = size
        self.start = start_off
        self.end = start_off + size


def read_box(f: io.BufferedReader, start_off: int) -> Mp4Box | None:
    f.seek(start_off)
    hdr = f.read(8)
    if len(hdr) < 8:
        return None
    size, typ = struct.unpack('>I4s', hdr)
    if size == 1:
        largesize = struct.unpack('>Q', f.read(8))[0]
        size = largesize
        box_start = start_off
        box_end = start_off + size
        return Mp4Box(typ, size, start_off)
    return Mp4Box(typ, size, start_off)
