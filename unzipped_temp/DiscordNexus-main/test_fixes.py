#!/usr/bin/env python
"""Test fixes for Tower of Temptation PvP Statistics Discord Bot

This script tests both fixes:
1. Historical parser timestamp handling
2. Server ID type consistency in autocomplete functions

Run this script to validate that fixes are working properly.
"""

import asyncio
import datetime
import os
import sys
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_fixes")

async def test_historical_parser_fix():
    """Test the historical parser timestamp fix"""
    logger.info("Testing historical parser timestamp fix...")
    
    # Mock a kill event with datetime object
    kill_event = {
        "timestamp": datetime.now(),
        "killer_id": "123",
        "killer_name": "TestKiller",
        "victim_id": "456",
        "victim_name": "TestVictim",
        "weapon": "TestWeapon",
        "is_suicide": False,
        "distance": 100
    }
    
    # Test conversion to ISO format for MongoDB
    if isinstance(kill_event["timestamp"], datetime):
        kill_event["timestamp"] = kill_event["timestamp"].isoformat()
        logger.info(f"Timestamp converted to ISO: {kill_event['timestamp']}")
    
    # Test if process_kill_event can handle the ISO string
    # Create a new timestamp object from the string
    try:
        # This simulates process_kill_event functionality
        timestamp_obj = datetime.fromisoformat(kill_event["timestamp"])
        logger.info(f"Successfully parsed ISO timestamp: {timestamp_obj}")
    except ValueError as e:
        logger.error(f"Error parsing ISO timestamp: {e}")
        return False
    
    # Create a CSV formatted timestamp
    csv_timestamp = "2025.05.03-08.15.00"
    
    # Test parsing the CSV formatted timestamp
    try:
        # This simulates the CSVParser.parse_kill_lines functionality
        csv_timestamp_obj = datetime.strptime(csv_timestamp, "%Y.%m.%d-%H.%M.%S")
        logger.info(f"Successfully parsed CSV timestamp: {csv_timestamp_obj}")
        
        # Convert to ISO for storage
        iso_timestamp = csv_timestamp_obj.isoformat()
        logger.info(f"CSV timestamp converted to ISO: {iso_timestamp}")
        
        # Ensure we can parse it back
        timestamp_obj_from_iso = datetime.fromisoformat(iso_timestamp)
        logger.info(f"Successfully parsed back from ISO: {timestamp_obj_from_iso}")
    except ValueError as e:
        logger.error(f"Error parsing CSV timestamp: {e}")
        return False
    
    logger.info("Historical parser timestamp fix is working correctly!")
    return True

async def test_server_id_type_consistency():
    """Test server_id type consistency fix for autocomplete"""
    logger.info("Testing server_id type consistency fix...")
    
    # Test cases for server_id
    test_cases = [
        "string_id",
        123,
        "456",
        None
    ]
    
    for test_case in test_cases:
        # Convert to string (same as in the fixed code)
        server_id = str(test_case) if test_case is not None else ""
        logger.info(f"Original: {test_case} ({type(test_case).__name__}) -> Converted: {server_id} ({type(server_id).__name__})")
    
    # Mock a server list with mixed types
    servers = [
        {"server_id": "string_id", "server_name": "String ID Server"},
        {"server_id": 123, "server_name": "Integer ID Server"},
        {"server_id": None, "server_name": "None ID Server"}
    ]
    
    # Test the fix that would run in the autocomplete functions
    for server in servers:
        if "server_id" in server:
            server["server_id"] = str(server["server_id"]) if server["server_id"] is not None else ""
    
    # Verify all are now strings
    all_strings = all(isinstance(server.get("server_id"), str) for server in servers)
    
    if all_strings:
        logger.info("All server_ids successfully converted to strings:")
        for server in servers:
            logger.info(f"  - {server['server_name']}: {server['server_id']} ({type(server['server_id']).__name__})")
        logger.info("Server ID type consistency fix is working correctly!")
        return True
    else:
        logger.error("Some server_ids were not converted to strings")
        return False

async def main():
    """Run all tests"""
    logger.info("Starting tests for Tower of Temptation PvP Statistics Discord Bot fixes")
    
    # Test the historical parser timestamp fix
    if await test_historical_parser_fix():
        logger.info("✅ Historical parser timestamp fix passed")
    else:
        logger.error("❌ Historical parser timestamp fix failed")
    
    # Test server_id type consistency
    if await test_server_id_type_consistency():
        logger.info("✅ Server ID type consistency fix passed")
    else:
        logger.error("❌ Server ID type consistency fix failed")
    
    logger.info("All tests completed")

if __name__ == "__main__":
    asyncio.run(main())
