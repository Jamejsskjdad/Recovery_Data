#!/usr/bin/env python3
"""Debug script để kiểm tra logic scan"""

def test_scan_logic():
    """Test logic scan với dữ liệu giả"""
    print("=== Testing Scan Logic ===")
    
    # Simulate MFT records
    test_records = [
        {"rec_id": 1, "name": "file1.txt", "in_use": True, "fn": True},
        {"rec_id": 2, "name": "file2.txt", "in_use": False, "fn": True},  # deleted
        {"rec_id": 3, "name": None, "in_use": False, "fn": False},  # deleted without filename
        {"rec_id": 4, "name": "file4.txt", "in_use": True, "fn": True},
        {"rec_id": 5, "name": "file5.txt", "in_use": False, "fn": True},  # deleted
    ]
    
    items = []
    deleted_count = 0
    existing_count = 0
    
    for rec in test_records:
        if rec["fn"]:
            name = rec["name"]
        else:
            name = f"Unknown_Record_{rec['rec_id']}"
        
        item = {
            "record": rec["rec_id"],
            "name": name,
            "status": "existing" if rec["in_use"] else "deleted",
            "size": 1024
        }
        
        items.append(item)
        
        if not rec["in_use"]:
            deleted_count += 1
            print(f"  Found deleted file: {name}")
        else:
            existing_count += 1
    
    print(f"\nResults:")
    print(f"Total files: {len(items)}")
    print(f"Deleted files: {deleted_count}")
    print(f"Existing files: {existing_count}")
    
    return deleted_count > 0

def main():
    print("=== Debug Scan Test ===")
    
    success = test_scan_logic()
    
    if success:
        print("\n✅ Scan logic test passed!")
        print("The logic should find deleted files correctly.")
    else:
        print("\n❌ Scan logic test failed!")

if __name__ == "__main__":
    main()
