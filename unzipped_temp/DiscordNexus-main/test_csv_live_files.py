"""
Test the CSV parser with actual CSV files from both old and new formats

This script tests the CSV parser's ability to correctly process both old format
CSV files (without console information) and new format CSV files (with console information)
from the test directories.
"""

import asyncio
import sys
import logging
import os
from typing import Dict, Any, List, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("csv_parser_test")

# Import the parsers
try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from utils.parsers import CSVParser
except ImportError:
    logger.error("Failed to import CSVParser. Make sure you're running from project root.")
    sys.exit(1)

# Test file paths
OLD_FORMAT_FILE = "test_sftp_dir/79.127.236.1_7020/actual1/deathlogs/world_1/2025.03.27-00.00.00.csv"
NEW_FORMAT_FILE = "attached_assets/2025.05.01-00.00.00.csv"

async def test_csv_file_parsing():
    """Test CSV parsing with actual files"""
    
    print("\n===== TESTING CSV PARSER WITH ACTUAL FILES =====")
    
    # Test old format file
    if os.path.exists(OLD_FORMAT_FILE):
        print(f"\n----- Testing Old Format CSV File: {OLD_FORMAT_FILE} -----")
        try:
            with open(OLD_FORMAT_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            print(f"Read {len(lines)} lines from old format file")
            
            # Process a sample of lines (first 5)
            sample_lines = lines[:5]
            print("\nSample lines from old format file:")
            for i, line in enumerate(sample_lines):
                print(f"{i+1}: {line.strip()}")
            
            # Parse the sample lines
            print("\nParsing sample lines:")
            for i, line in enumerate(sample_lines):
                result = CSVParser.parse_kill_line(line)
                if result:
                    print(f"✅ Line {i+1} parsed successfully")
                    print(f"   Timestamp: {result['timestamp']}")
                    print(f"   Killer: {result['killer_name']} ({result['killer_id']})")
                    print(f"   Victim: {result['victim_name']} ({result['victim_id']})")
                    print(f"   Weapon: {result['weapon']}")
                    print(f"   Console data: killer={result['killer_console']}, victim={result['victim_console']}")
                else:
                    print(f"❌ Failed to parse line {i+1}")
            
            # Process all lines
            all_events = CSVParser.parse_kill_lines(lines)
            print(f"\nProcessed {len(all_events)} out of {len(lines)} lines from old format file")
            
            # Count special cases
            suicides = sum(1 for event in all_events if event.get('is_suicide', False))
            console_events = sum(1 for event in all_events if event.get('killer_console') or event.get('victim_console'))
            
            print(f"Suicides: {suicides}")
            print(f"Events with console info: {console_events}")
            
        except Exception as e:
            print(f"❌ Error processing old format file: {e}")
    else:
        print(f"❌ Old format file not found at {OLD_FORMAT_FILE}")
    
    # Test new format file with console information
    if os.path.exists(NEW_FORMAT_FILE):
        print(f"\n----- Testing New Format CSV File: {NEW_FORMAT_FILE} -----")
        try:
            with open(NEW_FORMAT_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            print(f"Read {len(lines)} lines from new format file")
            
            # Process a sample of lines (first 5)
            sample_lines = lines[:5]
            print("\nSample lines from new format file:")
            for i, line in enumerate(sample_lines):
                print(f"{i+1}: {line.strip()}")
            
            # Parse the sample lines
            print("\nParsing sample lines:")
            for i, line in enumerate(sample_lines):
                result = CSVParser.parse_kill_line(line)
                if result:
                    print(f"✅ Line {i+1} parsed successfully")
                    print(f"   Timestamp: {result['timestamp']}")
                    print(f"   Killer: {result['killer_name']} ({result['killer_id']})")
                    print(f"   Victim: {result['victim_name']} ({result['victim_id']})")
                    print(f"   Weapon: {result['weapon']}")
                    print(f"   Console data: killer={result['killer_console']}, victim={result['victim_console']}")
                    if result.get('is_suicide', False):
                        print(f"   Suicide type: {result['suicide_type']}")
                else:
                    print(f"❌ Failed to parse line {i+1}")
            
            # Process all lines
            all_events = CSVParser.parse_kill_lines(lines)
            print(f"\nProcessed {len(all_events)} out of {len(lines)} lines from new format file")
            
            # Count special cases
            suicides = sum(1 for event in all_events if event.get('is_suicide', False))
            console_ps5 = sum(1 for event in all_events if event.get('killer_console') == "PS5" or event.get('victim_console') == "PS5")
            console_xsx = sum(1 for event in all_events if event.get('killer_console') == "XSX" or event.get('victim_console') == "XSX")
            
            print(f"Suicides: {suicides}")
            print(f"PS5 events: {console_ps5}")
            print(f"XSX events: {console_xsx}")
            
        except Exception as e:
            print(f"❌ Error processing new format file: {e}")
    else:
        print(f"❌ New format file not found at {NEW_FORMAT_FILE}")
    
    print("\n===== CSV PARSER TESTING COMPLETE =====")

if __name__ == "__main__":
    asyncio.run(test_csv_file_parsing())