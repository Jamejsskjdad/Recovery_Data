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

from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
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
    # Sử dụng GetLogicalDrives vì nó đáng tin cậy hơn
    roots = []
    try:
        drives_mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if drives_mask & (1 << i):
                letter = chr(65 + i)
                roots.append(f"{letter}:\\")
    except Exception as e:
        print(f"GetLogicalDrives failed: {e}")
        # Fallback: manual check
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{letter}:\\"
            try:
                if os.path.exists(drive):
                    roots.append(drive)
            except:
                pass
    
    print(f"Found roots: {roots}")
    return roots

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
        letter = root[:2]                       # 'C:'
        raw_path = r"\\.\{}".format(letter)     # đường dẫn raw để scan
        
        # Thêm tất cả ổ đĩa có thể truy cập được qua shutil
        # (DeviceWindows test có thể fail nếu không có quyền Administrator)
        try:
            # Test xem có thể mở device không (optional)
            test_dev = DeviceWindows(raw_path, readonly=True)
            test_dev.close()
            has_raw_access = True
        except Exception:
            # Không có quyền Administrator, nhưng vẫn hiển thị ổ đĩa
            has_raw_access = False
            
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
        self._update_counter = 0  # Counter for UI updates
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
            record_count = 0
            total_processed = 0
            for rec_id, rec in iter_mft_records(dev, boot):
                if self._stop:
                    break
                
                record_count += 1
                total_processed += 1
                if record_count % 5000 == 0:  # Update less frequently for large scans
                    deleted_count = sum(1 for item in self._items if item["status"] == "deleted")
                    existing_count = len(self._items) - deleted_count
                    self.status.emit(f"Scanned {record_count} records, found {len(self._items)} files ({deleted_count} deleted, {existing_count} existing)...")
                
                # Always process the record, regardless of filename
                if rec.fn is None:
                    # Record without filename - might be deleted or system file
                    name = f"Unknown_Record_{rec_id}"
                    parent = None
                    self._names[rec_id] = (name, parent, rec.is_dir)
                else:
                    # Record with filename
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
                
                # Emit files with smart batching to prevent UI blocking
                if not rec.in_use:  # deleted files - emit immediately
                    self.found.emit(item)
                    # Debug logging
                    if len(self._items) % 1000 == 0:  # Log every 1000th deleted file
                        print(f"Found deleted file: {name} (record {rec_id})")
                else:
                    # existing files - emit very infrequently to reduce UI load
                    self._update_counter += 1
                    if self._update_counter % 100 == 0:  # Emit every 100th existing file
                        self.found.emit(item)
                
                # Allow large scans but with better memory management
                if len(self._items) > 500000:  # Increase limit to 500k files for thorough scan
                    self.status.emit(f"Stopping scan: Found {len(self._items)} files (limit reached)")
                    break

            # reconstruct paths once we gathered names
            self.status.emit("Reconstructing paths ...")
            index: Dict[int, Tuple[str, Optional[int], bool]] = dict(self._names)

            def build_path(rid: int) -> Optional[str]:
                # Simplified path building to avoid infinite loops
                segs = []
                seen = set()
                cur = rid
                max_depth = 10  # Prevent infinite loops
                depth = 0
                
                while cur in index and cur not in seen and depth < max_depth:
                    seen.add(cur)
                    nm, parent, is_dir = index[cur]
                    segs.append(nm)
                    if parent is None:
                        break
                    cur = int(parent)
                    depth += 1
                
                if not segs:
                    return None
                return "/".join(reversed(segs))

            # Skip path reconstruction for large datasets to prevent UI blocking
            if len(self._items) > 50000:  # Higher threshold for large scans
                self.status.emit(f"Skipping path reconstruction for {len(self._items)} files (large dataset)")
                # Just use file names as paths for large datasets
                for it in self._items:
                    it["path"] = it["name"]
            else:
                # Only do path reconstruction for smaller datasets
                batch_size = 100  # Larger batch size for efficiency
                processed_count = 0
                
                for i in range(0, len(self._items), batch_size):
                    if self._stop:
                        break
                        
                    batch = self._items[i:i+batch_size]
                    for it in batch:
                        if self._stop:
                            break
                        p = build_path(it["record"]) or it["name"]
                        it["path"] = p
                        self.found.emit({"update": True, **it})  # notify UI to update path text
                        processed_count += 1
                    
                    # Update status every 1000 items
                    if processed_count % 1000 == 0:
                        self.status.emit(f"Reconstructing paths... ({processed_count}/{len(self._items)})")
                    
                    # Give UI a chance to process events
                    if not self._stop:
                        self.msleep(10)  # Very short delay

            # Count deleted files
            deleted_count = sum(1 for item in self._items if item["status"] == "deleted")
            existing_count = len(self._items) - deleted_count
            
            # Show summary immediately
            self.status.emit(f"Scan complete! Found {len(self._items)} files ({deleted_count} deleted, {existing_count} existing)")
            
            # Emit all remaining files that weren't emitted during scan
            self.status.emit("Loading all files into UI...")
            for i, item in enumerate(self._items):
                if i % 1000 == 0:  # Update progress every 1000 files
                    self.status.emit(f"Loading files... ({i}/{len(self._items)})")
                self.found.emit(item)
            
            # Update the filter to show deleted files by default
            self.show_deleted_btn.setChecked(True)
            self.show_all_btn.setChecked(False)
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
        drives = list_fixed_drives()
        
        if not drives:
            item = QListWidgetItem("No accessible drives found. Make sure you're running as Administrator.")
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.listw.addItem(item)
            return
            
        for d in drives:
            gb_total = d.total / (1024**3) if d.total else 0
            gb_free = d.free / (1024**3) if d.free else 0
            
            # Thêm thông tin về loại ổ đĩa
            drive_type = "Fixed" if d.type == 3 else "Removable" if d.type == 2 else "Unknown"
            
            text = f"{d.label}  ({d.letter})  —  {gb_total:.2f} GB total, {gb_free:.2f} GB free  [{drive_type}]"
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
        self.back_btn.clicked.connect(self._on_back)
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
        
        # Add filter buttons
        self.show_deleted_btn = QPushButton("Show Deleted Only")
        self.show_deleted_btn.setCheckable(True)
        self.show_deleted_btn.setChecked(True)  # Default to show deleted files
        self.show_deleted_btn.clicked.connect(self._on_filter_changed)
        search_row.addWidget(self.show_deleted_btn)
        
        self.show_all_btn = QPushButton("Show All")
        self.show_all_btn.setCheckable(True)
        self.show_all_btn.clicked.connect(self._on_filter_changed)
        search_row.addWidget(self.show_all_btn)
        
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
    
    def _on_filter_changed(self):
        # Ensure only one button is checked
        sender = self.sender()
        if sender == self.show_deleted_btn:
            self.show_all_btn.setChecked(False)
        else:
            self.show_deleted_btn.setChecked(False)
        self._apply_filter()
    
    def _on_back(self):
        # Stop scan if running
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, 
                "Stop Scan?", 
                "A scan is currently running. Do you want to stop it and go back?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._stop()
                # Wait a bit for the thread to stop
                QTimer.singleShot(500, lambda: self.back.emit())
            return
        self.back.emit()

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
            self.status.setText("Stopping scan...")
            # Force stop after a timeout
            QTimer.singleShot(2000, self._force_stop)
    
    def _force_stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(1000)  # Wait up to 1 second
            self._on_finished()

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

        # Create new tree item
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
            # Add deleted files at the top
            self.tree.insertTopLevelItem(0, node)
        else:
            # Add existing files at the bottom
            self.tree.addTopLevelItem(node)
        
        # Update status to show current count (less frequently for large datasets)
        total_items = self.tree.topLevelItemCount()
        if total_items % 1000 == 0:  # Update less frequently
            self.status.setText(f"Displaying {total_items} files...")
        
        # Limit the number of items to prevent UI slowdown
        if self.tree.topLevelItemCount() > 10000:  # Higher limit for large scans
            # Remove oldest items (keep deleted files)
            while self.tree.topLevelItemCount() > 5000:  # Keep more items
                self.tree.takeTopLevelItem(self.tree.topLevelItemCount() - 1)

    @Slot()
    def _on_finished(self):
        self.status.setText("Scan completed")
        self.progress.setRange(0, 1)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Apply filter and show count
        self._apply_filter()
        
        # Force refresh
        self.tree.update()
        
        # Show summary in status
        total_items = self.tree.topLevelItemCount()
        deleted_count = sum(1 for i in range(total_items) if self.tree.topLevelItem(i).text(2) == "deleted")
        self.status.setText(f"Scan completed. Total files: {total_items} ({deleted_count} deleted)")

    def _apply_filter(self):
        q = self.search.text().lower().strip()
        show_deleted_only = self.show_deleted_btn.isChecked()
        show_all = self.show_all_btn.isChecked()
        
        visible_count = 0
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            text = (it.text(0) + " " + it.text(1)).lower()
            status = it.text(2).lower()
            
            # Apply text filter
            text_match = q == "" or q in text
            
            # Apply status filter
            status_match = True
            if show_deleted_only:
                status_match = status == "deleted"
            elif show_all:
                status_match = True
            
            is_visible = text_match and status_match
            it.setHidden(not is_visible)
            
            if is_visible:
                visible_count += 1
        
        # Update status to show filtered count
        self.status.setText(f"Showing {visible_count} of {self.tree.topLevelItemCount()} files")


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

