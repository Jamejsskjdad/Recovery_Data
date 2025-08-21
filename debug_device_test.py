#!/usr/bin/env python3
"""Debug script để test DeviceWindows với từng ổ đĩa"""

from pyrecover.core.device_windows import DeviceWindows
import shutil

def test_device_access():
    drives = ['C:', 'D:', 'E:']
    
    for drive in drives:
        print(f"\n=== Testing {drive} ===")
        
        # Test 1: shutil.disk_usage
        try:
            usage = shutil.disk_usage(f"{drive}\\")
            print(f"  shutil.disk_usage: OK - {usage.total / (1024**3):.2f} GB")
        except Exception as e:
            print(f"  shutil.disk_usage: FAIL - {e}")
            continue
        
        # Test 2: DeviceWindows
        raw_path = f"\\\\.\\{drive}"
        try:
            print(f"  Trying to open: {raw_path}")
            dev = DeviceWindows(raw_path, readonly=True)
            print(f"  DeviceWindows: OK")
            dev.close()
        except Exception as e:
            print(f"  DeviceWindows: FAIL - {e}")
            continue
        
        print(f"  ✓ {drive} is accessible")

if __name__ == "__main__":
    test_device_access()
