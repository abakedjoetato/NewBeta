"""
Test the log parser with the provided Deadside.log file

This script tests the log parser's ability to extract player connection events
and other events from the provided Deadside.log file.
"""

import asyncio
import sys
import logging
import os
import re
from typing import Dict, Any, List, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("log_parser_test")

# Import the parser
try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from utils.parsers import LogParser
except ImportError:
    logger.error("Failed to import LogParser. Make sure you're running from project root.")
    sys.exit(1)

# Path to the log file
LOG_FILE_PATH = "attached_assets/Deadside.log"

async def test_log_parser():
    """Test the log parser with the provided log file"""
    
    print("\n----- LOG PARSER TESTING -----")
    
    if not os.path.exists(LOG_FILE_PATH):
        print(f"❌ Log file not found at {LOG_FILE_PATH}")
        return
    
    print(f"Reading log file: {LOG_FILE_PATH}")
    
    try:
        with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
        
        print(f"Read {len(log_lines)} lines from log file")
        
        # Extract log lines with player connections
        connection_regex = r'\[([\d\.\-]+)-([\d\.]+)\].*Player ([^\s]+) \(([0-9a-f]+)\) (connected|disconnected)'
        
        connection_lines = []
        for line in log_lines:
            if re.search(connection_regex, line):
                connection_lines.append(line.strip())
        
        print(f"Found {len(connection_lines)} connection events")
        
        # Process a subset of the connection lines (up to 5)
        for i, line in enumerate(connection_lines[:5]):
            print(f"\nProcessing connection line {i+1}: {line}")
            result = LogParser.parse_log_line(line)
            if result:
                print(f"✅ Successfully parsed connection event:")
                print(f"   Timestamp: {result['timestamp']}")
                print(f"   Player: {result['player_name']} ({result['player_id']})")
                print(f"   Action: {result['action']}")
                print(f"   Platform: {result['platform']}")
            else:
                print(f"❌ Failed to parse connection event")
        
        # Extract log lines with game events
        event_lines = []
        for line in log_lines:
            if "[Game]" in line:
                event_lines.append(line.strip())
        
        print(f"\nFound {len(event_lines)} game events")
        
        # Process a subset of the event lines (up to 5)
        for i, line in enumerate(event_lines[:5]):
            print(f"\nProcessing game event line {i+1}: {line}")
            result = LogParser.parse_log_line(line)
            if result:
                print(f"✅ Successfully parsed game event:")
                print(f"   Timestamp: {result['timestamp']}")
                print(f"   Event type: {result['event_type']}")
                print(f"   Details: {result['details']}")
            else:
                print(f"❌ Failed to parse game event")
                
        # Test the line batch processing function
        print("\nTesting batch processing of log lines...")
        events, connections = LogParser.parse_log_lines(connection_lines[:10])
        print(f"Batch processed {len(connections)} connection events and {len(events)} other events")
        
    except Exception as e:
        print(f"❌ Error testing log parser: {e}")
    
    print("\nLog parser testing complete!")

if __name__ == "__main__":
    asyncio.run(test_log_parser())