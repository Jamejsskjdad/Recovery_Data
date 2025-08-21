from __future__ import annotations

MAGIC = {
    'jpg': [b'\xFF\xD8\xFF'],
    'png': [b'\x89PNG\r\n\x1a\n'],
    'zip': [b'PK\x03\x04'],
    'mp4': [b'\x00\x00\x00', b'ftyp'],  # kiểm tra 4 bytes đầu + "ftyp"
}
