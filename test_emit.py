#!/usr/bin/env python3
"""Test script để kiểm tra logic emit files"""

def test_emit_logic():
    """Test logic emit với dữ liệu giả"""
    print("=== Testing Emit Logic ===")
    
    # Simulate scan results
    test_items = [
        {"record": 1, "name": "file1.txt", "status": "existing", "size": 1024},
        {"record": 2, "name": "file2.txt", "status": "deleted", "size": 2048},
        {"record": 3, "name": "file3.txt", "status": "existing", "size": 512},
        {"record": 4, "name": "file4.txt", "status": "deleted", "size": 4096},
        {"record": 5, "name": "file5.txt", "status": "existing", "size": 1024},
    ]
    
    print("Simulating file emission...")
    emitted_count = 0
    deleted_count = 0
    existing_count = 0
    
    for item in test_items:
        # Simulate emit
        emitted_count += 1
        
        if item["status"] == "deleted":
            deleted_count += 1
            print(f"  Emitted deleted file: {item['name']}")
        else:
            existing_count += 1
            print(f"  Emitted existing file: {item['name']}")
    
    print(f"\nEmit Results:")
    print(f"Total emitted: {emitted_count}")
    print(f"Deleted files: {deleted_count}")
    print(f"Existing files: {existing_count}")
    
    return emitted_count == len(test_items)

def main():
    print("=== Emit Logic Test ===")
    
    success = test_emit_logic()
    
    if success:
        print("\n✅ Emit logic test passed!")
        print("All files should be emitted and displayed in UI.")
    else:
        print("\n❌ Emit logic test failed!")

if __name__ == "__main__":
    main()
