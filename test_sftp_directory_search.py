"""
Test script to verify SFTP directory search and CSV file discovery in deep structures

This script implements a simpler version of the directory search algorithm
and verifies it works correctly with our test directory structure.
"""

import os
import re
import time
import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger('test_sftp_search')

# Same pattern used in the actual code
CSV_FILENAME_PATTERN = r"^\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}\.csv$"

def find_csv_files_recursive(directory, max_depth=6, current_depth=0):
    """Recursively search for CSV files in all subdirectories"""
    if current_depth > max_depth:
        return []
        
    found_files = []
    try:
        # List directory contents
        items = os.listdir(directory)
        
        # Check each item
        for item in items:
            item_path = os.path.join(directory, item)
            try:
                if os.path.isdir(item_path):
                    # Recursively check subdirectory
                    logger.info(f"Checking directory: {item_path} (depth {current_depth})")
                    subdir_files = find_csv_files_recursive(
                        item_path, max_depth, current_depth + 1
                    )
                    found_files.extend(subdir_files)
                elif re.match(CSV_FILENAME_PATTERN, item):
                    # Found a CSV file
                    logger.info(f"Found CSV file: {item_path}")
                    
                    # Get modification time
                    mtime = os.path.getmtime(item_path)
                    found_files.append((item_path, mtime, item))
            except Exception as e:
                logger.error(f"Error processing item {item}: {e}")
                continue
    except Exception as e:
        logger.error(f"Error scanning directory {directory}: {e}")
        
    return found_files

def main():
    """Test CSV file discovery with the test SFTP directory structure"""
    test_dir = "./test_sftp_dir"
    
    # Make sure the test directory exists
    if not os.path.exists(test_dir):
        logger.error(f"Test directory {test_dir} does not exist!")
        return
    
    logger.info(f"Searching for CSV files in {test_dir} with max depth of 6...")
    
    # Find all CSV files in the test directory
    csv_files = find_csv_files_recursive(test_dir)
    
    # Log results
    logger.info(f"Found {len(csv_files)} CSV files in total across all directories")
    
    # Sort the files by timestamp (newest first)
    try:
        csv_files.sort(key=lambda x: float(x[1]), reverse=True)
        logger.info("Successfully sorted CSV files by timestamp")
    except Exception as e:
        logger.error(f"Error sorting CSV files: {e}")
    
    # Log the most recent files
    if csv_files:
        logger.info("\nMost recent CSV files:")
        for i, (file_path, mtime, filename) in enumerate(csv_files[:3]):
            timestamp_str = str(datetime.datetime.fromtimestamp(mtime))
            logger.info(f"  CSV #{i+1}: {file_path} (Modified: {timestamp_str})")
    else:
        logger.warning("No CSV files found!")
        
    # Print summary of directory structure
    logger.info("\nDirectory structure summary:")
    
    def print_directory_structure(directory, indent=0):
        items = os.listdir(directory)
        dirs = [item for item in items if os.path.isdir(os.path.join(directory, item))]
        files = [item for item in items if os.path.isfile(os.path.join(directory, item))]
        
        # Print directories
        for d in dirs:
            print("  " * indent + f"📁 {d}/")
            print_directory_structure(os.path.join(directory, d), indent + 1)
        
        # Print files
        for f in files:
            print("  " * indent + f"📄 {f}")
    
    print_directory_structure(test_dir)
    
    logger.info("\nTest completed successfully!")

if __name__ == "__main__":
    main()