# gui_app.py
# PyRecover GUI – EaseUS-like 2-step flow: pick drive → scan (existing + deleted)
# Requirements: PySide6, pywin32; run terminal as Administrator when scanning raw drives.

from __future__ import annotations
import sys
import os
import ctypes
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# --- Make sure project root is on sys.path so `import pyrecover...` works ---
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ensure pyrecover is a package (the folder should have an __init__.py). If not, we still try via sys.path above.

# Back-end imports (use the code you already have)
try:
    from pyrecover.core.device_windows import DeviceWindows
    from pyrecover.fs.ntfs.boot import parse_boot_sector, NtfsBoot
    from pyrecover.fs.ntfs.mft import iter_mft_records, MftRecord
except Exception as e:
    raise SystemExit(f"❌ Could not import pyrecover modules: {e}\nMake sure `pyrecover/` folder is next to this file and contains __init__.py.")

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QProgressBar, QTreeWidget,
    QTreeWidgetItem, QLineEdit, QSplitter, QMessageBox
)

# ------------------------ Windows drive helpers ------------------------
import shutil

GetLogicalDriveStringsW = ctypes.windll.kernel32.GetLogicalDriveStringsW
GetDriveTypeW           = ctypes.windll.kernel32.GetDriveTypeW
GetVolumeInformationW   = ctypes.windll.kernel32.GetVolumeInformationW

@dataclass
class DriveInfo:
    letter: str
    path: str
    label: str
    total: int
    free: int
    type: int  # keep for display (0..6)

def _get_roots() -> list[str]:
    buf_len = 1024
    buf = ctypes.create_unicode_buffer(buf_len)
    GetLogicalDriveStringsW(buf_len, buf)
    return [d for d in buf.value.split("\x00") if d]  # 'C:\\', 'D:\\', ...

def list_fixed_drives() -> List[DriveInfo]:
    """Liệt kê mọi volume có thể truy cập (không phân biệt FIXED/REMOVABLE).
    Ổ nào không đọc được dung lượng sẽ tự bị bỏ qua."""
    out: List[DriveInfo] = []
    for root in _get_roots():
        # lấy dung lượng bằng shutil (ổ không truy cập được sẽ ném OSError)
        try:
            usage = shutil.disk_usage(root)  # total, used, free (bytes)
        except Exception:
            continue

        # label best‑effort
        label = root
        vol_name_buf = ctypes.create_unicode_buffer(256)
        fs_name_buf  = ctypes.create_unicode_buffer(256)
        sn = ctypes.c_ulong(0); mcl = ctypes.c_ulong(0); fs_flags = ctypes.c_ulong(0)
        try:
            GetVolumeInformationW(
                ctypes.c_wchar_p(root),
                vol_name_buf, 256,
                ctypes.byref(sn), ctypes.byref(mcl), ctypes.byref(fs_flags),
                fs_name_buf, 256
            )
            if vol_name_buf.value:
                label = vol_name_buf.value
        except Exception:
            pass

        # type chỉ để tham khảo
        dtyp = GetDriveTypeW(ctypes.c_wchar_p(root))
        letter = root[:2]                       # 'D:'
        raw_path = r"\\.\{}".format(letter)     # đường dẫn raw để scan
        out.append(DriveInfo(
            letter=letter,
            path=raw_path,
            label=label,
            total=usage.total,
            free=usage.free,
            type=dtyp
        ))
    return out




# ------------------------ Scanner thread ------------------------
class ScanWorker(QThread):
    found = Signal(dict)          # emits item dict
    status = Signal(str)          # status text
    started_scan = Signal()
    finished_scan = Signal()

    def __init__(self, device_path: str):
        super().__init__()
        self.device_path = device_path
        self._stop = False
        self._items: List[dict] = []
        # cache for path reconstruction
        self._names: Dict[int, Tuple[str, Optional[int], bool]] = {}  # rec_id -> (name, parent, is_dir)

    def stop(self):
        self._stop = True

    def run(self):
        self.started_scan.emit()
        try:
            self.status.emit(f"Opening {self.device_path} ...")
            dev = DeviceWindows(self.device_path, readonly=True)
            try:
                boot = parse_boot_sector(dev.read(0, 512))
            except Exception as e:
                self.status.emit(f"Boot sector parse failed: {e}")
                dev.close()
                self.finished_scan.emit()
                return

            self.status.emit("Scanning $MFT ... (this may take a while)")
            for rec_id, rec in iter_mft_records(dev, boot):
                if self._stop:
                    break
                if rec.fn is None:
                    continue
                name = rec.fn.name
                parent = rec.fn.parent_ref if rec.fn else None
                self._names[rec_id] = (name, parent, rec.is_dir)

                # Determine basic size if resident
                size = 0
                try:
                    if rec.data and rec.data.resident_data is not None:
                        size = len(rec.data.resident_data)
                    # Non-resident: we don't parse initialized size in this MVP
                except Exception:
                    pass

                item = {
                    "record": rec_id,
                    "name": name,
                    "path": None,           # fill later
                    "is_dir": rec.is_dir,
                    "status": "existing" if rec.in_use else "deleted",
                    "size": size,
                }
                self._items.append(item)
                # emit quickly for responsiveness
                self.found.emit(item)

            # reconstruct paths once we gathered names
            self.status.emit("Reconstructing paths ...")
            index: Dict[int, Tuple[str, Optional[int], bool]] = dict(self._names)

            def build_path(rid: int) -> Optional[str]:
                segs = []
                seen = set()
                cur = rid
                while cur in index and cur not in seen:
                    seen.add(cur)
                    nm, parent, is_dir = index[cur]
                    segs.append(nm)
                    if parent is None:
                        break
                    cur = int(parent)
                if not segs:
                    return None
                return "/".join(reversed(segs))

            for it in self._items:
                p = build_path(it["record"]) or it["name"]
                it["path"] = p
                self.found.emit({"update": True, **it})  # notify UI to update path text

            self.status.emit("Done.")
        except Exception as e:
            self.status.emit(f"Scan error: {e}")
        finally:
            try:
                dev.close()
            except Exception:
                pass
            self.finished_scan.emit()

# ------------------------ UI ------------------------
class DrivePickerPage(QWidget):
    drive_chosen = Signal(DriveInfo)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        self.title = QLabel("Select a location to search for lost data")
        self.title.setStyleSheet("font-size:18px; font-weight:600;")
        lay.addWidget(self.title)

        self.listw = QListWidget()
        self.listw.setStyleSheet("QListWidget{font-size:14px}")
        lay.addWidget(self.listw)

        self.refresh_btn = QPushButton("Refresh drives")
        self.refresh_btn.clicked.connect(self.populate)
        lay.addWidget(self.refresh_btn)

        self.populate()
        self.listw.itemDoubleClicked.connect(self._on_double)

    def populate(self):
        self.listw.clear()
        for d in list_fixed_drives():
            gb_total = d.total / (1024**3) if d.total else 0
            gb_free = d.free / (1024**3) if d.free else 0
            text = f"{d.label}  ({d.letter})  —  {gb_total:.2f} GB total, {gb_free:.2f} GB free"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, d)
            self.listw.addItem(item)

    def _on_double(self, item: QListWidgetItem):
        d: DriveInfo = item.data(Qt.UserRole)
        self.drive_chosen.emit(d)


class ScanPage(QWidget):
    back = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        top = QHBoxLayout()
        self.info = QLabel("Drive: -")
        self.back_btn = QPushButton("← Back")
        self.back_btn.clicked.connect(self.back.emit)
        top.addWidget(self.back_btn)
        top.addWidget(self.info)
        top.addStretch(1)
        outer.addLayout(top)

        # Search box
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Filter:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type to filter by name or path ...")
        search_row.addWidget(self.search)
        outer.addLayout(search_row)

        # Progress + status
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        outer.addWidget(self.progress)
        self.status = QLabel("…")
        outer.addWidget(self.status)

        # Tree results
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Path", "Status", "Size", "Record#"])
        self.tree.setColumnWidth(0, 280)
        outer.addWidget(self.tree)

        # Start/Stop
        row = QHBoxLayout()
        self.start_btn = QPushButton("Start Scan")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        row.addStretch(1)
        outer.addLayout(row)

        self.worker: Optional[ScanWorker] = None
        self.device_path: Optional[str] = None

        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        self.search.textChanged.connect(self._apply_filter)

    def set_drive(self, d: DriveInfo):
        self.device_path = d.path
        self.info.setText(f"Drive {d.letter} — {d.label}  |  Device: {d.path}")
        self.tree.clear()

    @Slot()
    def _start(self):
        if not self.device_path:
            QMessageBox.warning(self, "No drive", "Please pick a drive first")
            return
        if self.worker and self.worker.isRunning():
            return
        self.tree.clear()
        self.status.setText("Preparing scan …")
        self.progress.setRange(0, 0)
        self.worker = ScanWorker(self.device_path)
        self.worker.found.connect(self._on_found)
        self.worker.status.connect(self.status.setText)
        self.worker.started_scan.connect(lambda: (self.start_btn.setEnabled(False), self.stop_btn.setEnabled(True)))
        self.worker.finished_scan.connect(self._on_finished)
        self.worker.start()

    @Slot()
    def _stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()

    @Slot(dict)
    def _on_found(self, item: dict):
        # If it's an update, try to modify existing row
        if item.get("update"):
            rec = str(item["record"]) 
            # simple linear search; dataset is big so could be optimized, but fine for MVP
            for i in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(i)
                if it.text(4) == rec:
                    it.setText(1, item.get("path") or "")
                    break
            return

        node = QTreeWidgetItem()
        node.setText(0, item.get("name", ""))
        node.setText(1, item.get("path") or "")
        node.setText(2, item.get("status", ""))
        node.setText(3, str(item.get("size", 0)))
        node.setText(4, str(item.get("record", "")))
        # color code deleted
        if item.get("status") == "deleted":
            node.setForeground(0, Qt.red)
            node.setForeground(2, Qt.red)
        self.tree.addTopLevelItem(node)

    @Slot()
    def _on_finished(self):
        self.status.setText("Scan completed")
        self.progress.setRange(0, 1)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._apply_filter()

    def _apply_filter(self):
        q = self.search.text().lower().strip()
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            text = (it.text(0) + " " + it.text(1)).lower()
            it.setHidden(q not in text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyRecover – Data Recovery (Prototype)")
        self.resize(1100, 700)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.page_pick = DrivePickerPage()
        self.page_scan = ScanPage()

        self.stack.addWidget(self.page_pick)
        self.stack.addWidget(self.page_scan)
        self.stack.setCurrentWidget(self.page_pick)

        self.page_pick.drive_chosen.connect(self._on_drive)
        self.page_scan.back.connect(lambda: self.stack.setCurrentWidget(self.page_pick))

    @Slot(DriveInfo)
    def _on_drive(self, d: DriveInfo):
        self.page_scan.set_drive(d)
        self.stack.setCurrentWidget(self.page_scan)


def main():
    app = QApplication(sys.argv)

    # --- Check for Admin privileges, required for raw drive access ---
    is_admin = False
    try:
        # POSIX
        is_admin = (os.getuid() == 0)
    except AttributeError:
        # Windows
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

    if not is_admin:
        QMessageBox.critical(
            None,
            "Administrator Privileges Required",
            "This application must be run as an administrator to scan drives.\n\nPlease right-click the file and select 'Run as administrator'."
        )
        sys.exit(1)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

