import os
import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_csv_finder')

async def find_csv_files_recursive(directory, max_depth=4, current_depth=0):
    """Recursively search for CSV files in all subdirectories"""
    logger.info(f"Searching directory: {directory} (depth {current_depth})")
    
    # Limit recursion depth
    if current_depth > max_depth:
        logger.info(f"Max depth {max_depth} reached, stopping at {directory}")
        return []
            
    csv_files = []
    
    try:
        # Get directory contents
        items = os.listdir(directory)
        logger.info(f"Directory {directory} contains {len(items)} items")
        
        # First look for CSV files in current directory
        for item in items:
            # Check if it's a CSV file
            if item.lower().endswith('.csv'):
                item_path = os.path.join(directory, item)
                logger.info(f"Found CSV file: {item} in directory: {directory}")
                csv_files.append(item_path)
        
        # Process all subdirectories regardless of whether we've found files already
        for item in items:
            item_path = os.path.join(directory, item)
            
            try:
                # Skip if it's a CSV file (already processed)
                if item.lower().endswith('.csv'):
                    continue
                
                # Check if it's a directory and process recursively
                if os.path.isdir(item_path):
                    logger.info(f"Exploring subdirectory: {item_path} (depth {current_depth})")
                    subdirectory_files = await find_csv_files_recursive(
                        item_path, max_depth, current_depth + 1
                    )
                    if subdirectory_files:
                        logger.info(f"Found {len(subdirectory_files)} CSV files in {item_path}")
                        csv_files.extend(subdirectory_files)
                    
            except Exception as item_e:
                logger.warning(f"Error processing item {item_path}: {item_e}")
                continue
                
    except Exception as e:
        logger.error(f"Error listing directory {directory}: {e}")
        
    return csv_files

async def main():
    # Test directory
    test_dir = "test_sftp_dir"
    
    # Find all CSV files
    csv_files = await find_csv_files_recursive(test_dir)
    
    # Show results
    if csv_files:
        logger.info(f"Found a total of {len(csv_files)} CSV files")
        logger.info(f"CSV paths found in directories: {set([os.path.dirname(p) for p in csv_files])}")
        
        for file_path in csv_files:
            logger.info(f"CSV file: {file_path}")
    else:
        logger.warning("No CSV files found in any directory")

if __name__ == "__main__":
    asyncio.run(main())