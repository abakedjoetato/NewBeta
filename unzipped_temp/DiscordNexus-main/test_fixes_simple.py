"""
Simplified test script for Tower of Temptation PvP Statistics Bot Fixes
"""

import sys
import logging
import os
import datetime

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("csv_parser_test")

# Test data
old_format_line = "2025.05.01-12.34.56;KillerName;12345678;VictimName;87654321;M4A1;120"
new_format_line = "2025.05.01-12.34.56;KillerName;12345678;VictimName;87654321;M4A1;120;XSX;PS5"
suicide_line = "2025.05.01-12.34.56;PlayerName;12345678;PlayerName;12345678;suicide_by_relocation;0;XSX;XSX"

# Import the parser
try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from utils.parsers import CSVParser
except ImportError:
    logger.error("Failed to import CSVParser. Make sure you're running from project root.")
    sys.exit(1)

def test_csv_parser():
    """Test the CSV parser with various line formats"""
    
    print("\n----- CSV PARSER TESTING -----")
    
    # Test old format
    print("\nTesting old format line:")
    result = CSVParser.parse_kill_line(old_format_line)
    if result:
        print(f"✅ Successfully processed old format line")
        print(f"   Timestamp: {result['timestamp']}")
        print(f"   Killer: {result['killer_name']} ({result['killer_id']})")
        print(f"   Victim: {result['victim_name']} ({result['victim_id']})")
        print(f"   Weapon: {result['weapon']}")
    else:
        print("❌ Failed to process old format line")

    # Test new format with console fields
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
    
    # Test suicide
    print("\nTesting suicide line:")
    result = CSVParser.parse_kill_line(suicide_line)
    if result and result['is_suicide']:
        print(f"✅ Successfully processed suicide line")
        print(f"   Suicide type: {result['suicide_type']}")
        print(f"   Weapon: {result['weapon']}")
    else:
        print("❌ Failed to process suicide line")
    
    # Test timestamp parsing
    print("\n----- TIMESTAMP PARSING -----")
    timestamp_str = "2025.05.01-12.34.56"
    try:
        timestamp = datetime.datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
        print(f"✅ Successfully parsed timestamp: {timestamp}")
    except ValueError:
        print(f"❌ Failed to parse timestamp")
        
    # Test multiple format
    timestamp_str = "2025-05-01-12.34.56"
    try:
        timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d-%H.%M.%S")
        print(f"✅ Successfully parsed alternative timestamp: {timestamp}")
    except ValueError:
        print(f"❌ Failed to parse alternative timestamp")
        
    print("\nAll tests completed!")

if __name__ == "__main__":
    test_csv_parser()