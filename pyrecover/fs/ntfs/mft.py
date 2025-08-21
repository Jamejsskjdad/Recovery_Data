from __future__ import annotations
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Iterable
from .boot import NtfsBoot

FILE_SIG = b"FILE"

@dataclass
class DataRun:
    lcn: int
    length: int  # clusters

@dataclass
class FileNameAttr:
    parent_ref: int
    name: str
    flags: int

@dataclass
class DataAttr:
    non_resident: bool
    runs: List[DataRun] = field(default_factory=list)
    resident_data: bytes | None = None

@dataclass
class MftRecord:
    record_num: Optional[int]
    in_use: bool
    is_dir: bool
    base_ref: Optional[int]
    fn: Optional[FileNameAttr]
    data: Optional[DataAttr]


def _apply_fixup(record: bytearray, sector_size: int) -> bool:
    # FILE record header: offset 4: usa_ofs (2), offset 6: usa_count (2)
    if record[0:4] != FILE_SIG:
        return False
    usa_ofs, usa_count = struct.unpack_from('<HH', record, 4)
    if usa_ofs == 0 or usa_count == 0:
        return False
    usn = struct.unpack_from('<H', record, usa_ofs)[0]
    # USA array entries (after the first USN) replace last 2 bytes of each sector
    count_sectors = usa_count - 1
    for i in range(count_sectors):
        off = (i+1) * sector_size - 2
        expected = record[off:off+2]
        if expected != struct.pack('<H', usn):
            return False  # torn record
        newv = struct.unpack_from('<H', record, usa_ofs + 2 + 2*i)[0]
        record[off:off+2] = struct.pack('<H', newv)
    return True


def _iter_attrs(buf: bytes, first_attr_ofs: int) -> Iterable[Tuple[int, bytes]]:
    o = first_attr_ofs
    while o + 8 <= len(buf):
        atype = struct.unpack_from('<I', buf, o)[0]
        if atype == 0xFFFFFFFF:
            break
        alen = struct.unpack_from('<I', buf, o+4)[0]
        if alen == 0 or o + alen > len(buf):
            break
        yield atype, buf[o:o+alen]
        o += alen


def _parse_filename_attr(attr: bytes) -> FileNameAttr | None:
    # Resident value starts at value_offset
    non_resident = attr[8]
    if non_resident:
        return None
    value_len = struct.unpack_from('<I', attr, 16)[0]
    value_ofs = struct.unpack_from('<H', attr, 20)[0]
    v = attr[value_ofs:value_ofs+value_len]
    if len(v) < 66:
        return None
    parent_ref = struct.unpack_from('<Q', v, 0)[0] & ((1<<48)-1)  # low 48 bits
    name_len = v[64]
    name_ns  = v[65]
    name = v[66:66+name_len*2].decode('utf-16le', errors='replace')
    flags = struct.unpack_from('<I', v, 56)[0]
    return FileNameAttr(parent_ref=parent_ref, name=name, flags=flags)


def _decode_mapping_pairs(mp: bytes) -> List[DataRun]:
    runs: List[DataRun] = []
    i = 0
    lcn = 0
    while i < len(mp):
        header = mp[i]
        i += 1
        if header == 0:
            break
        size_len = header & 0x0F
        off_len  = (header >> 4) & 0x0F
        if size_len == 0:
            break
        run_len = int.from_bytes(mp[i:i+size_len], 'little', signed=False)
        i += size_len
        run_off_bytes = mp[i:i+off_len]
        i += off_len
        # sign-extend the offset
        if off_len == 0:
            lcn_delta = 0
        else:
            sign = 1 << (8*off_len - 1)
            val = int.from_bytes(run_off_bytes, 'little', signed=False)
            if val & sign:
                val = val - (1 << (8*off_len))
            lcn_delta = val
        lcn += lcn_delta
        runs.append(DataRun(lcn=lcn, length=run_len))
    return runs


def _parse_data_attr(attr: bytes) -> DataAttr | None:
    non_resident = attr[8]
    if not non_resident:
        value_len = struct.unpack_from('<I', attr, 16)[0]
        value_ofs = struct.unpack_from('<H', attr, 20)[0]
        data = attr[value_ofs:value_ofs+value_len]
        return DataAttr(non_resident=False, resident_data=data)
    # Non-resident
    mapping_ofs = struct.unpack_from('<H', attr, 32)[0]
    data_size   = struct.unpack_from('<Q', attr, 48)[0]
    mp = attr[mapping_ofs:]
    runs = _decode_mapping_pairs(mp)
    return DataAttr(non_resident=True, runs=runs)


def parse_mft_record(raw: bytes, sector_size: int) -> MftRecord | None:
    if len(raw) < 48:
        return None
    buf = bytearray(raw)
    if not _apply_fixup(buf, sector_size):
        return None
    # basic header
    first_attr_ofs = struct.unpack_from('<H', buf, 20)[0]
    flags = struct.unpack_from('<H', buf, 22)[0]
    in_use = bool(flags & 0x0001)
    is_dir = bool(flags & 0x0002)
    base_ref = struct.unpack_from('<Q', buf, 32)[0]
    base_ref = (base_ref & ((1<<48)-1)) if base_ref else None

    fn: FileNameAttr | None = None
    data: DataAttr | None = None

    for atype, abuf in _iter_attrs(buf, first_attr_ofs):
        if atype == 0x30:  # FILE_NAME
            fn = _parse_filename_attr(abuf) or fn
        elif atype == 0x80:  # DATA
            data = _parse_data_attr(abuf) or data

    return MftRecord(
        record_num=None,
        in_use=in_use,
        is_dir=is_dir,
        base_ref=base_ref,
        fn=fn,
        data=data,
    )


def iter_mft_records(dev, boot: NtfsBoot, max_records: int = 2_000_000) -> Iterable[Tuple[int, MftRecord]]:
    """Duyệt MFT thô: đọc liên tiếp các record có kích thước boot.mft_record_size.
    *Heuristic*: dừng khi gặp chuỗi dài record vô hiệu.
    """
    rec_size = boot.mft_record_size
    mft_off = boot.lcn_to_off(boot.mft_lcn)
    bad = 0
    for idx in range(max_records):
        off = mft_off + idx * rec_size
        try:
            raw = dev.read(off, rec_size)
        except Exception:
            break
        rec = parse_mft_record(raw, boot.sector_size)
        if rec is None:
            bad += 1
            if bad > 1024:
                break
            continue
        bad = 0
        rec.record_num = idx
        yield idx, rec
