# pyrecover/core/device_windows.py
from __future__ import annotations
import win32file, win32con, win32security, win32api

def _enable_privileges(names):
    hProc = win32api.GetCurrentProcess()
    hTok = win32security.OpenProcessToken(
        hProc, win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY
    )
    privs = []
    for n in names:
        try:
            luid = win32security.LookupPrivilegeValue(None, n)
            privs.append((luid, win32con.SE_PRIVILEGE_ENABLED))
        except Exception:
            pass
    if privs:
        win32security.AdjustTokenPrivileges(hTok, False, privs)

class DeviceWindows:
    def __init__(self, path: str, readonly: bool = True) -> None:
        _enable_privileges([
            win32security.SE_BACKUP_NAME,
            win32security.SE_RESTORE_NAME,
            win32security.SE_MANAGE_VOLUME_NAME
        ])
        
        # Xử lý path - hỗ trợ cả drive letter và raw device path
        if len(path) == 2 and path[1] == ':':
            # Nếu là drive letter như "C:", chuyển thành raw device path
            device_path = "\\\\.\\" + path
        elif path.startswith("\\\\.\\"):
            # Đã là raw device path
            device_path = path
        else:
            # Có thể là file path
            device_path = path
            
        access = win32con.GENERIC_READ
        share = (win32con.FILE_SHARE_READ |
                 win32con.FILE_SHARE_WRITE |
                 win32con.FILE_SHARE_DELETE)
        
        try:
            self.handle = win32file.CreateFile(
                device_path,
                access,
                share,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None
            )
            self.path = device_path
        except Exception as e:
            raise IOError(f"Failed to open device {device_path}: {e}")

    def read(self, offset: int, size: int) -> bytes:
        # pywin32 SetFilePointer(handle, distance, moveMethod)
        win32file.SetFilePointer(self.handle, offset, win32con.FILE_BEGIN)
        hr, data = win32file.ReadFile(self.handle, size)
        if hr not in (0, None):
            raise IOError(f"ReadFile failed hr={hr}")
        if len(data) != size:
            # có thể do đọc chạm cuối volume → để robust, bạn có thể tùy chọn trả về phần đã đọc
            raise IOError(f"Short read at off={offset}, want={size}, got={len(data)}")
        return data

    def close(self):
        try:
            self.handle.Close()
        except Exception:
            pass
        self.handle = None
