"""Debug script to trace SFTP CSV file discovery

This script provides enhanced logging to trace exactly what happens during
the CSV file discovery process, with extra logging to help diagnose why
files aren't being found on the production server.
"""

import os
import re
import asyncio
import logging
from pathlib import Path

# Setup logging with maximum verbosity
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('debug_csv_find')

# Define patterns that match our CSV files
CSV_FILENAME_PATTERN = r'^\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}\.csv$'

async def find_csv_files_recursive(directory, max_depth=6, current_depth=0, starting_dir=None):
    """Recursively search for CSV files in all subdirectories with enhanced logging
    
    Args:
        directory: The directory to search
        max_depth: Maximum recursion depth 
        current_depth: Current recursion depth
        starting_dir: The initial directory we started search from
    """
    # Set starting_dir on first call to prevent going back beyond starting point
    if starting_dir is None:
        starting_dir = directory
    
    logger.debug(f"TRACE: Searching directory: {directory} (depth {current_depth})")
    logger.debug(f"TRACE: starting_dir = {starting_dir}")
    
    # Limit recursion depth to prevent deep searches
    if current_depth > max_depth:
        logger.warning(f"TRACE: Max depth {max_depth} reached, stopping at {directory}")
        return []
        
    csv_files = []
    
    try:
        # Get directory contents
        items = sorted(os.listdir(directory))
        logger.debug(f"TRACE: Directory {directory} contains {len(items)} items: {items[:10]}{'...' if len(items) > 10 else ''}")
        
        # First look for CSV files in current directory
        csv_in_dir = [item for item in items if re.match(CSV_FILENAME_PATTERN, item)]
        logger.debug(f"TRACE: CSV matches in {directory}: {csv_in_dir}")
        
        for item in csv_in_dir:
            item_path = os.path.join(directory, item)
            logger.info(f"TRACE: Found CSV file: {item} in directory: {directory}")
            csv_files.append(item_path)
        
        # Process all subdirectories regardless of whether we've found files already
        dirs_in_path = []
        for item in items:
            item_path = os.path.join(directory, item)
            
            # Skip if it's a file (we only want to recurse into directories)
            if os.path.isfile(item_path):
                continue
                
            # If it's a directory, we'll explore it recursively
            if os.path.isdir(item_path):
                dirs_in_path.append(item)
                # Only explore directories that are under the starting directory path
                if not item_path.startswith(starting_dir):
                    logger.debug(f"TRACE: Skipping directory outside of search scope: {item_path}")
                    continue
                    
                logger.debug(f"TRACE: Exploring subdirectory: {item_path} (depth {current_depth})")
                subdirectory_files = await find_csv_files_recursive(
                    item_path, max_depth, current_depth + 1, starting_dir
                )
                
                if subdirectory_files:
                    logger.info(f"TRACE: Found {len(subdirectory_files)} CSV files in {item_path}")
                    csv_files.extend(subdirectory_files)
                else:
                    logger.debug(f"TRACE: No CSV files found in subdirectory: {item_path}")
        
        # Important: Summarize directories explored at this level
        logger.debug(f"TRACE: Subdirectories at {directory}: {dirs_in_path}")
                
    except Exception as e:
        logger.error(f"TRACE: Error listing directory {directory}: {e}", exc_info=True)
        
    return csv_files

async def test_with_sftp_structure():
    """Test CSV file discovery with the test SFTP directory structure"""
    test_dir = "test_sftp_dir"
    
    # 1. Try the entire test directory
    logger.info(f"===== TESTING FULL STRUCTURE =====")
    csv_files = await find_csv_files_recursive(test_dir)
    
    if csv_files:
        logger.info(f"Found a total of {len(csv_files)} CSV files")
        for file_path in csv_files:
            logger.info(f"CSV file: {file_path}")
    else:
        logger.warning("No CSV files found in any directory")
    
    # 2. Try from the server ID directory
    logger.info(f"\n===== TESTING FROM SERVER ID DIRECTORY =====")
    server_id_dir = os.path.join(test_dir, "79.127.236.1_7020")
    csv_files = await find_csv_files_recursive(server_id_dir)
    
    if csv_files:
        logger.info(f"Found a total of {len(csv_files)} CSV files")
        for file_path in csv_files:
            logger.info(f"CSV file: {file_path}")
    else:
        logger.warning("No CSV files found in any directory")
    
    # 3. Try from the actual1 directory
    logger.info(f"\n===== TESTING FROM ACTUAL1 DIRECTORY =====")
    actual1_dir = os.path.join(server_id_dir, "actual1")
    csv_files = await find_csv_files_recursive(actual1_dir)
    
    if csv_files:
        logger.info(f"Found a total of {len(csv_files)} CSV files")
        for file_path in csv_files:
            logger.info(f"CSV file: {file_path}")
    else:
        logger.warning("No CSV files found in any directory")
    
    # 4. Try from the deathlogs directory
    logger.info(f"\n===== TESTING FROM DEATHLOGS DIRECTORY =====")
    deathlogs_dir = os.path.join(actual1_dir, "deathlogs")
    csv_files = await find_csv_files_recursive(deathlogs_dir)
    
    if csv_files:
        logger.info(f"Found a total of {len(csv_files)} CSV files")
        for file_path in csv_files:
            logger.info(f"CSV file: {file_path}")
    else:
        logger.warning("No CSV files found in any directory")

async def main():
    await test_with_sftp_structure()

if __name__ == "__main__":
    asyncio.run(main())