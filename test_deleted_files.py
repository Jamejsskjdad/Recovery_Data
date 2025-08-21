#!/usr/bin/env python3
"""Test script để kiểm tra việc scan deleted files"""

from pyrecover.gui_app import list_fixed_drives
from pyrecover.core.device_windows import DeviceWindows
from pyrecover.fs.ntfs.boot import parse_boot_sector
from pyrecover.fs.ntfs.mft import iter_mft_records

def test_deleted_files_scan():
    """Test scan deleted files trên ổ đĩa"""
    print("=== Testing Deleted Files Scan ===")
    
    # Get first available drive
    drives = list_fixed_drives()
    if not drives:
        print("❌ No drives available")
        return False
    
    drive = drives[0]  # Use first drive
    print(f"Testing on drive: {drive.letter} ({drive.label})")
    
    try:
        # Open device
        dev = DeviceWindows(drive.path, readonly=True)
        boot = parse_boot_sector(dev.read(0, 512))
        
        # Scan for deleted files
        deleted_count = 0
        existing_count = 0
        total_records = 0
        
        print("Scanning MFT records...")
        for rec_id, rec in iter_mft_records(dev, boot):
            total_records += 1
            
            if total_records > 10000:  # Limit for testing
                break
                
            if rec.fn is None:
                # Record without filename
                if not rec.in_use:
                    deleted_count += 1
                else:
                    existing_count += 1
            else:
                # Record with filename
                if not rec.in_use:
                    deleted_count += 1
                    print(f"  Found deleted file: {rec.fn.name} (record {rec_id})")
                else:
                    existing_count += 1
            
            if total_records % 1000 == 0:
                print(f"  Scanned {total_records} records: {deleted_count} deleted, {existing_count} existing")
        
        dev.close()
        
        print(f"\n=== Scan Results ===")
        print(f"Total records scanned: {total_records}")
        print(f"Deleted files found: {deleted_count}")
        print(f"Existing files found: {existing_count}")
        print(f"Deletion rate: {deleted_count/(deleted_count+existing_count)*100:.1f}%")
        
        return deleted_count > 0
        
    except Exception as e:
        print(f"❌ Error during scan: {e}")
        return False

def main():
    print("=== Deleted Files Test Suite ===")
    
    # Test deleted files scan
    print("\n1. Testing Deleted Files Scan")
    success = test_deleted_files_scan()
    
    # Summary
    print("\n=== Summary ===")
    if success:
        print("✅ Deleted files scan test passed!")
        print("\nImprovements made:")
        print("- Fixed logic to include records without filenames")
        print("- Added priority for deleted files in UI")
        print("- Added filter buttons (Show Deleted Only / Show All)")
        print("- Better status reporting with deleted vs existing counts")
        print("- Deleted files shown at top of list")
    else:
        print("❌ Deleted files scan test failed.")

if __name__ == "__main__":
    main()
