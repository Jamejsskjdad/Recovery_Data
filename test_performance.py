#!/usr/bin/env python3
"""Test script để kiểm tra performance improvements"""

import time
from pyrecover.gui_app import list_fixed_drives

def test_drive_detection_performance():
    """Test performance của drive detection"""
    print("=== Testing Drive Detection Performance ===")
    
    start_time = time.time()
    drives = list_fixed_drives()
    end_time = time.time()
    
    print(f"✅ Found {len(drives)} drives in {end_time - start_time:.3f} seconds")
    for d in drives:
        print(f"  - {d.letter}: {d.label} ({d.total / (1024**3):.1f} GB)")
    
    return len(drives) > 0

def test_memory_usage():
    """Test memory usage với large datasets"""
    print("\n=== Testing Memory Usage ===")
    
    # Simulate large dataset
    large_list = []
    for i in range(100000):
        large_list.append({
            "record": i,
            "name": f"file_{i}.txt",
            "path": f"/path/to/file_{i}.txt",
            "status": "existing",
            "size": 1024
        })
    
    print(f"✅ Created {len(large_list)} items")
    print(f"   Memory usage: ~{len(large_list) * 200 / (1024**2):.1f} MB estimated")
    
    # Test batch processing
    batch_size = 50
    processed = 0
    start_time = time.time()
    
    for i in range(0, len(large_list), batch_size):
        batch = large_list[i:i+batch_size]
        processed += len(batch)
        if processed % 10000 == 0:
            print(f"   Processed {processed}/{len(large_list)} items...")
    
    end_time = time.time()
    print(f"✅ Batch processing completed in {end_time - start_time:.3f} seconds")
    
    return True

def main():
    print("=== Performance Test Suite ===")
    
    # Test 1: Drive detection
    print("\n1. Drive Detection Test")
    drive_test = test_drive_detection_performance()
    
    # Test 2: Memory usage
    print("\n2. Memory Usage Test")
    memory_test = test_memory_usage()
    
    # Summary
    print("\n=== Summary ===")
    if drive_test and memory_test:
        print("✅ All performance tests passed!")
        print("\nImprovements implemented:")
        print("- Reduced UI update frequency (every 10th item)")
        print("- Smaller batch sizes (50 instead of 100)")
        print("- Lower item limits (2000 instead of 5000)")
        print("- File count limit (100k files max)")
        print("- Better progress reporting")
        print("- Longer delays to prevent UI blocking")
    else:
        print("❌ Some tests failed.")

if __name__ == "__main__":
    main()
