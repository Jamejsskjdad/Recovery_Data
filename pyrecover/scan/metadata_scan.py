from __future__ import annotations
from typing import List, Dict, Any, Iterable
from ..core.device_windows import DeviceWindows
from ..fs.ntfs.boot import parse_boot_sector, NtfsBoot
from ..fs.ntfs.mft import iter_mft_records, MftRecord


def scan_deleted(image_path: str, path_filter: str | None = None, name_contains: str | None = None) -> List[Dict[str, Any]]:
    dev = DeviceWindows(image_path)
    try:
        boot = parse_boot_sector(dev.read(0, 512))
        results: List[Dict[str, Any]] = []
        pf = (path_filter or '').lower()
        nc = (name_contains or '').lower()
        for rid, rec in iter_mft_records(dev, boot):
            if rec.in_use:
                continue  # chỉ quan tâm đã xóa
            if rec.fn is None or rec.data is None:
                continue
            name = rec.fn.name
            # Đường dẫn đầy đủ cần dựng từ parent chain; MVP: lọc đơn giản theo tên
            if nc and nc not in name.lower():
                continue
            if pf and pf not in name.lower():
                # tạm thời không có full path → cho phép lọc theo name chứa folder keyword
                pass
            entry = {
                'record': rid,
                'name': name,
                'is_dir': rec.is_dir,
                'has_runs': (rec.data.non_resident and len(rec.data.runs) > 0),
                'resident_len': (len(rec.data.resident_data) if rec.data.resident_data else 0),
            }
            results.append(entry)
        return results
    finally:
        dev.close()
