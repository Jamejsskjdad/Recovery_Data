from __future__ import annotations
import os
from typing import Optional
from ..core.device_windows import DeviceWindows
from ..fs.ntfs.boot import parse_boot_sector, NtfsBoot
from ..fs.ntfs.mft import iter_mft_records

CHUNK = 4 * 1024 * 1024

def export_record(image_path: str, record_id: int, out_path: str) -> None:
    dev = DeviceWindows(r"\\.\D:")
    try:
        boot = parse_boot_sector(dev.read(0, 512))
        cluster_size = boot.cluster_size
        for rid, rec in iter_mft_records(dev, boot):
            if rid != record_id:
                continue
            if rec.data is None:
                raise RuntimeError("No DATA attribute")
            if rec.data.resident_data is not None:
                with open(out_path, 'wb') as f:
                    f.write(rec.data.resident_data)
                return
            if not rec.data.runs:
                raise RuntimeError("Non-resident DATA has no runs")
            # Xuất tuần tự theo runlist
            with open(out_path, 'wb') as f:
                for run in rec.data.runs:
                    if run.lcn <= 0 or run.length <= 0:
                        continue
                    off = boot.lcn_to_off(run.lcn)
                    total = run.length * cluster_size
                    remaining = total
                    cur = off   
                    while remaining > 0:
                        to_read = min(remaining, CHUNK)
                        buf = dev.read(cur, to_read)
                        f.write(buf)
                        cur += to_read
                        remaining -= to_read
                return
        raise RuntimeError(f"Record {record_id} not found")
    finally:
        dev.close()
