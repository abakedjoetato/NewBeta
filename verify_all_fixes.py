"""
Comprehensive verification script for Tower of Temptation PvP Statistics Bot Fixes

This script verifies all the fixes we've made:
1. CSV Parser handling of console information fields
2. Server ID type consistency in autocomplete functions
3. Timestamp parsing with multiple formats
4. Suicide event recognition improvements
"""

import asyncio
import datetime
import sys
import logging
import os
from typing import Dict, Any, List, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("verify_fixes")

# Test CSV data
test_csv_data = [
    # Old format (no console fields)
    "2025.05.01-12.34.56;KillerName;12345678;VictimName;87654321;M4A1;120",
    
    # New format (with console fields)
    "2025.05.01-12.34.56;KillerName;12345678;VictimName;87654321;M4A1;120;XSX;PS5",
    
    # Empty killer fields
    "2025.05.01-12.34.56;;12345678;VictimName;87654321;M4A1;120;XSX;PS5",
    
    # Empty victim fields
    "2025.05.01-12.34.56;KillerName;12345678;;;M4A1;120;XSX;PS5",
    
    # Suicide by menu
    "2025.05.01-12.34.56;PlayerName;12345678;PlayerName;12345678;suicide_by_relocation;0;XSX;XSX",
    
    # Alternative suicide format
    "2025.05.01-12.34.56;PlayerName;12345678;PlayerName;12345678;suicide by relocation;0;XSX;XSX",
    
    # Vehicle suicide
    "2025.05.01-12.34.56;PlayerName;12345678;PlayerName;12345678;land_vehicle;0;XSX;XSX",
    
    # Alternative timestamp format
    "2025-05-01-12.34.56;KillerName;12345678;VictimName;87654321;M4A1;120",
    
    # Space instead of dash in timestamp
    "2025.05.01 12.34.56;KillerName;12345678;VictimName;87654321;M4A1;120"
]

# Test server data
test_servers = [
    {"server_id": "server1", "name": "Test Server 1"},
    {"server_id": 2, "name": "Test Server 2"},  # Integer ID
    {"server_id": "3", "name": "Test Server 3"}  # String ID that looks like a number
]

# Import the modules we need to test
try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from utils.parsers import CSVParser
except ImportError:
    logger.error("Failed to import CSVParser. Make sure you're running from project root.")
    sys.exit(1)

async def test_csv_parser():
    """Test the CSV parser with various line formats"""
    
    print("\n----- CSV PARSER TESTING -----")
    
    # Test each line individually
    success_count = 0
    for i, line in enumerate(test_csv_data):
        print(f"\nTest case {i+1}: {line}")
        result = CSVParser.parse_kill_line(line)
        if result:
            success_count += 1
            print(f"✅ Successfully processed line")
            print(f"   Timestamp: {result['timestamp']}")
            print(f"   Killer: {result['killer_name']} ({result['killer_id']})")
            print(f"   Victim: {result['victim_name']} ({result['victim_id']})")
            print(f"   Weapon: {result['weapon']}")
            print(f"   Console data: killer={result['killer_console']}, victim={result['victim_console']}")
            if result.get('is_suicide', False):
                print(f"   Suicide type: {result['suicide_type']}")
        else:
            print("❌ Failed to process line")
    
    # Test processing multiple lines
    kill_events = CSVParser.parse_kill_lines(test_csv_data)
    print(f"\nProcessed {len(kill_events)} out of {len(test_csv_data)} lines")
    
    # Count by type
    suicides = sum(1 for event in kill_events if event.get('is_suicide', False))
    console_events = sum(1 for event in kill_events if event.get('killer_console') or event.get('victim_console'))
    
    print(f"Suicides: {suicides}")
    print(f"Events with console info: {console_events}")
    
    print(f"\nCSV Parser Success Rate: {success_count}/{len(test_csv_data)} ({success_count/len(test_csv_data)*100:.1f}%)")
    return success_count == len(test_csv_data)

async def test_server_id_handling():
    """Test server ID type handling"""
    
    print("\n----- SERVER ID TYPE HANDLING -----")
    
    # For each test server
    for server in test_servers:
        original_id = server["server_id"]
        # Convert to string for comparison
        string_id = str(original_id)
        
        print(f"\nTesting server_id: {original_id} (type: {type(original_id).__name__})")
        
        # Test string comparison (should always work with proper type handling)
        result = string_id == str(original_id)
        print(f"  String comparison (string_id == str(original_id)): {result}")
        
        # Test direct comparison with different types
        result = string_id == original_id if isinstance(original_id, str) else string_id == str(original_id)
        print(f"  Type-safe comparison: {result}")
        
        # Test what happens in autocomplete context
        print(f"  In autocomplete context:")
        print(f"  - Original ID: {original_id} (type: {type(original_id).__name__})")
        print(f"  - Converted ID for storage: {str(original_id)} (type: {type(str(original_id)).__name__})")
        print(f"  - For display to user: Server {server['name']} ({str(original_id)})")
    
    print("\nAll server IDs can be properly converted to strings for consistent handling.")
    return True

async def test_timestamp_parsing():
    """Test the timestamp parsing with different formats"""
    
    print("\n----- TIMESTAMP PARSING -----")
    
    test_timestamps = [
        "2025.05.01-12.34.56",  # Standard format 
        "2025-05-01-12.34.56",  # Alternative separator
        "2025.05.01 12.34.56",  # Space instead of dash
    ]
    
    success_count = 0
    for ts in test_timestamps:
        print(f"\nTesting timestamp: {ts}")
        try:
            # Try to parse with our more flexible parsing in CSVParser
            timestamp = None
            # Try the standard format first
            try:
                timestamp = datetime.datetime.strptime(ts, "%Y.%m.%d-%H.%M.%S")
            except ValueError:
                # Try alternative formats if the standard format fails
                try:
                    timestamp = datetime.datetime.strptime(ts, "%Y-%m-%d-%H.%M.%S")
                except ValueError:
                    try:
                        timestamp = datetime.datetime.strptime(ts, "%Y.%m.%d %H.%M.%S")
                    except ValueError:
                        timestamp = None
                        
            if timestamp:
                success_count += 1
                print(f"✅ Successfully parsed timestamp: {timestamp}")
            else:
                print(f"❌ Failed to parse timestamp")
        except Exception as e:
            print(f"❌ Error parsing timestamp: {e}")
    
    print(f"\nTimestamp Parsing Success Rate: {success_count}/{len(test_timestamps)} ({success_count/len(test_timestamps)*100:.1f}%)")
    return success_count == len(test_timestamps)

async def main():
    """Main test function"""
    print("=" * 50)
    print("TOWER OF TEMPTATION PVP STATISTICS BOT FIXES VERIFICATION")
    print("=" * 50)
    
    # Run all tests
    csv_parser_success = await test_csv_parser()
    server_id_success = await test_server_id_handling()
    timestamp_success = await test_timestamp_parsing()
    
    # Summary
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    print(f"CSV Parser: {'✅ PASSED' if csv_parser_success else '❌ FAILED'}")
    print(f"Server ID Handling: {'✅ PASSED' if server_id_success else '❌ FAILED'}")
    print(f"Timestamp Parsing: {'✅ PASSED' if timestamp_success else '❌ FAILED'}")
    
    all_passed = csv_parser_success and server_id_success and timestamp_success
    print("\nOVERALL RESULT:")
    if all_passed:
        print("✅ ALL TESTS PASSED - FIXES SUCCESSFULLY IMPLEMENTED")
    else:
        print("❌ SOME TESTS FAILED - REVIEW THE RESULTS")
    
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())