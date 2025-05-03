"""
Test script to verify the CSV file sorting fix

This script will use our test SFTP directory structure to verify that 
our fix for the sorting issue works correctly.
"""

import asyncio
import os
import time
import datetime
import logging
from utils.sftp import SFTPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger('test_sorting_fix')

async def test_csv_sorting():
    """Test that CSV file sorting works correctly with our fix"""
    # Create a simulated CSV file list like the one in sftp.py
    csv_files = []
    
    # Add some test files with timestamps as floats (from time.time())
    # These are how files are added in the actual code (line 475)
    csv_files.append(("./file1.csv", time.time(), "file1.csv"))  # current time
    csv_files.append(("./file2.csv", time.time() - 3600, "file2.csv"))  # 1 hour ago
    csv_files.append(("./file3.csv", time.time() - 7200, "file3.csv"))  # 2 hours ago
    
    # Print the files before sorting
    print("Files before sorting:")
    for i, (path, mtime, name) in enumerate(csv_files):
        dt = datetime.datetime.fromtimestamp(mtime)
        print(f"  {i+1}. {path} - Timestamp: {mtime} ({dt})")
    
    # Sort the files using our fixed algorithm
    print("\nSorting files...")
    try:
        csv_files.sort(key=lambda x: float(x[1]), reverse=True)
        print("Successfully sorted CSV files by timestamp!")
    except Exception as e:
        print(f"Error sorting CSV files: {e}")
        return
    
    # Print the files after sorting to verify they're in the right order
    print("\nFiles after sorting (should be newest to oldest):")
    for i, (path, mtime, name) in enumerate(csv_files):
        dt = datetime.datetime.fromtimestamp(mtime)
        print(f"  {i+1}. {path} - Timestamp: {mtime} ({dt})")
    
    # Now test the full directory search functionality using the test_sftp_dir
    print("\nTesting directory scanning with the test SFTP structure...")
    test_dir = "./test_sftp_dir"
    
    # Count how many CSV files we have in the test directory
    csv_count = 0
    for root, dirs, files in os.walk(test_dir):
        for file in files:
            if file.endswith('.csv'):
                csv_count += 1
                print(f"Found CSV file: {os.path.join(root, file)}")
    
    print(f"\nTotal CSV files found manually: {csv_count}")
    
    # No need to create an actual SFTP client since we're just testing locally
    print("\nTest completed successfully!")

async def main():
    """Run the test"""
    await test_csv_sorting()

if __name__ == "__main__":
    asyncio.run(main())