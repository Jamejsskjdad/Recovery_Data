import os
import shutil
import ctypes
from ctypes import wintypes

def debug_list_drives():
    """Debug function để kiểm tra ổ đĩa có sẵn"""
    print("=== DEBUG: List all drives ===")
    
    # Method 1: Using os.listdir
    try:
        drives = [f"{chr(i)}:" for i in range(ord('A'), ord('Z')+1) if os.path.exists(f"{chr(i)}:\\")]
        print(f"Method 1 (os.path.exists): {drives}")
    except Exception as e:
        print(f"Method 1 failed: {e}")
    
    # Method 2: Using shutil.disk_usage
    available_drives = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = f"{letter}:\\"
        try:
            usage = shutil.disk_usage(drive)
            available_drives.append(f"{letter}:")
            print(f"  {letter}: - {usage.total / (1024**3):.2f} GB total")
        except:
            pass
    
    print(f"Method 2 (shutil.disk_usage): {available_drives}")
    
    # Method 3: Using Windows API (if available)
    try:
        from ctypes import windll
        
        # GetLogicalDrives bitmask
        drives_mask = windll.kernel32.GetLogicalDrives()
        drives_list = []
        for i in range(26):
            if drives_mask & (1 << i):
                drives_list.append(f"{chr(65 + i)}:")
        print(f"Method 3 (GetLogicalDrives): {drives_list}")
        
        # GetLogicalDriveStrings
        buffer_size = 256
        buffer = ctypes.create_string_buffer(buffer_size)
        windll.kernel32.GetLogicalDriveStringsA(buffer_size, buffer)
        drives_str = buffer.value.decode('ascii').rstrip('\x00').split('\x00')
        drives_str = [d for d in drives_str if d]
        print(f"Method 4 (GetLogicalDriveStrings): {drives_str}")
        
    except Exception as e:
        print(f"Method 3&4 failed: {e}")

if __name__ == "__main__":
    debug_list_drives()
