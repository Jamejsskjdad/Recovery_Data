# pyrecover/core/device.py
from __future__ import annotations
import os
from typing import BinaryIO


class BlockDevice:
    def __init__(self, path: str, readonly: bool = True) -> None:
        mode = 'rb' if readonly else 'r+b'
        # buffering=0 để tránh bỏ qua seek/align; image file an toàn hơn raw device
        self._f: BinaryIO = open(path, mode, buffering=0)
        self._size = os.path.getsize(path)


    @property
    def size(self) -> int:
        return self._size


    def read(self, offset: int, size: int) -> bytes:
        if offset < 0 or offset + size > self._size:
            raise ValueError(f"Read out of bounds: off={offset} size={size} total={self._size}")
        self._f.seek(offset)
        data = self._f.read(size)
        if len(data) != size:
            raise IOError(f"Short read at off={offset} want={size} got={len(data)}")
        return data

    def close(self) -> None:
        try:
            self._f.close()
        except Exception:
            pass