"""
Test script to validate the CSV parser fix for handling console information fields

This script tests the CSV parser with both old format (without console fields)
and new format (with console fields) to ensure it correctly processes both types.
"""

import asyncio
import datetime
import sys
import logging
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("csv_parser_test")

# Mock data for testing
old_format_line = "2025.05.01-12.34.56;KillerName;12345678;VictimName;87654321;M4A1;120"
new_format_line = "2025.05.01-12.34.56;KillerName;12345678;VictimName;87654321;M4A1;120;XSX;PS5"
empty_killer_line = "2025.05.01-12.34.56;;12345678;VictimName;87654321;M4A1;120;XSX;PS5"
empty_victim_line = "2025.05.01-12.34.56;KillerName;12345678;;;M4A1;120;XSX;PS5"
suicide_line = "2025.05.01-12.34.56;PlayerName;12345678;PlayerName;12345678;suicide_by_relocation;0;XSX;XSX"
alt_suicide_line = "2025.05.01-12.34.56;PlayerName;12345678;PlayerName;12345678;suicide by relocation;0;XSX;XSX"

# Add path to the project modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the fixed parser module
try:
    from utils.parsers import CSVParser
except ImportError:
    logger.error("Failed to import CSVParser. Make sure you're running from project root.")
    sys.exit(1)

async def test_csv_parser():
    """Test the CSV parser with various line formats"""
    
    print("Testing old format line processing:")
    result = CSVParser.parse_kill_line(old_format_line)
    if result:
        print(f"✅ Successfully processed old format line")
        print(f"   Timestamp: {result['timestamp']}")
        print(f"   Killer: {result['killer_name']} ({result['killer_id']})")
        print(f"   Victim: {result['victim_name']} ({result['victim_id']})")
        print(f"   Weapon: {result['weapon']}")
        print(f"   Console data: killer={result['killer_console']}, victim={result['victim_console']}")
    else:
        print("❌ Failed to process old format line")

    print("\nTesting new format line (with console fields):")
    result = CSVParser.parse_kill_line(new_format_line)
    if result:
        print(f"✅ Successfully processed new format line")
        print(f"   Timestamp: {result['timestamp']}")
        print(f"   Killer: {result['killer_name']} ({result['killer_id']})")
        print(f"   Victim: {result['victim_name']} ({result['victim_id']})")
        print(f"   Weapon: {result['weapon']}")
        print(f"   Console data: killer={result['killer_console']}, victim={result['victim_console']}")
    else:
        print("❌ Failed to process new format line")

    print("\nTesting line with empty killer fields:")
    result = CSVParser.parse_kill_line(empty_killer_line)
    if result:
        print(f"✅ Successfully processed line with empty killer")
        print(f"   Timestamp: {result['timestamp']}")
        print(f"   Killer: {result['killer_name']} ({result['killer_id']})")
        print(f"   Victim: {result['victim_name']} ({result['victim_id']})")
        print(f"   Weapon: {result['weapon']}")
    else:
        print("❌ Failed to process line with empty killer")

    print("\nTesting line with empty victim fields:")
    result = CSVParser.parse_kill_line(empty_victim_line)
    if result:
        print(f"✅ Successfully processed line with empty victim")
        print(f"   Timestamp: {result['timestamp']}")
        print(f"   Killer: {result['killer_name']} ({result['killer_id']})")
        print(f"   Victim: {result['victim_name']} ({result['victim_id']})")
        print(f"   Weapon: {result['weapon']}")
    else:
        print("❌ Failed to process line with empty victim")

    print("\nTesting suicide line:")
    result = CSVParser.parse_kill_line(suicide_line)
    if result and result['is_suicide']:
        print(f"✅ Successfully processed suicide line")
        print(f"   Suicide type: {result['suicide_type']}")
        print(f"   Weapon: {result['weapon']}")
    else:
        print("❌ Failed to process suicide line")

    print("\nTesting alternate suicide format line:")
    result = CSVParser.parse_kill_line(alt_suicide_line)
    if result and result['is_suicide']:
        print(f"✅ Successfully processed alternate suicide format line")
        print(f"   Suicide type: {result['suicide_type']}")
        print(f"   Weapon: {result['weapon']}")
    else:
        print("❌ Failed to process alternate suicide format line")

    print("\nTesting multiple lines:")
    test_lines = [
        old_format_line,
        new_format_line,
        empty_killer_line,
        empty_victim_line,
        suicide_line,
        alt_suicide_line
    ]
    
    kill_events = CSVParser.parse_kill_lines(test_lines)
    print(f"✅ Processed {len(kill_events)} out of {len(test_lines)} lines")
    
    # Count by type
    suicides = sum(1 for event in kill_events if event.get('is_suicide', False))
    console_events = sum(1 for event in kill_events if event.get('killer_console') or event.get('victim_console'))
    
    print(f"   Suicides: {suicides}")
    print(f"   Events with console info: {console_events}")

async def main():
    """Main function to run tests"""
    await test_csv_parser()

if __name__ == "__main__":
    asyncio.run(main())