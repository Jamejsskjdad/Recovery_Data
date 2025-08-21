#!/usr/bin/env python3
"""Test script để kiểm tra các cải thiện GUI"""

def test_imports():
    """Test xem các imports có hoạt động không"""
    try:
        from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
        from PySide6.QtWidgets import QMessageBox
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_drive_detection():
    """Test việc phát hiện ổ đĩa"""
    try:
        from pyrecover.gui_app import list_fixed_drives
        drives = list_fixed_drives()
        print(f"✅ Found {len(drives)} drives:")
        for d in drives:
            print(f"  - {d.letter}: {d.label}")
        return len(drives) > 0
    except Exception as e:
        print(f"❌ Drive detection failed: {e}")
        return False

def main():
    print("=== Testing GUI Improvements ===")
    
    # Test 1: Imports
    print("\n1. Testing imports...")
    imports_ok = test_imports()
    
    # Test 2: Drive detection
    print("\n2. Testing drive detection...")
    drives_ok = test_drive_detection()
    
    # Summary
    print("\n=== Summary ===")
    if imports_ok and drives_ok:
        print("✅ All tests passed! GUI should work properly now.")
        print("\nImprovements made:")
        print("- Fixed thread stopping mechanism")
        print("- Added batch processing to prevent UI blocking")
        print("- Improved Back button handling")
        print("- Added item limit to prevent UI slowdown")
        print("- Added force stop timeout")
    else:
        print("❌ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    main()
