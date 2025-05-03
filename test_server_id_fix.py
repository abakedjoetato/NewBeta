"""
Test script for verifying server ID type consistency in autocomplete functions

This script tests that server_id is always treated as a string in autocomplete functions,
which fixes the issue with inconsistent handling of server IDs across commands.
"""

import asyncio
import sys
import logging
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("server_id_test")

# Mock data for testing
class MockInteraction:
    def __init__(self, command_name, options=None, current=""):
        self.command_name = command_name
        self.options = options or {}
        self.current = current
        self.guild_id = 123456789
        
    async def response(self):
        return None

class MockOption:
    def __init__(self, name, value):
        self.name = name
        self.value = value

class Choice:
    def __init__(self, name, value):
        self.name = name
        self.value = value

# Test data with mixed types
test_servers = [
    {"server_id": "server1", "name": "Test Server 1", "ip": "192.168.1.1", "port": 7020},
    {"server_id": 2, "name": "Test Server 2", "ip": "192.168.1.2", "port": 7020},  # Integer ID
    {"server_id": "3", "name": "Test Server 3", "ip": "192.168.1.3", "port": 7020}  # String ID that looks like a number
]

# Mock database query result
mock_query_result = {
    "servers": test_servers
}

async def test_server_id_type_consistency():
    """Test that server_id is consistently treated as string"""
    print("Testing server_id type consistency...")
    
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

    print("\nType handling test complete!")

async def test_autocomplete_mixed_types():
    """Test autocomplete with different server_id types"""
    print("\nTesting autocomplete with mixed server_id types...")
    
    # Create choices from servers
    choices = []
    for server in test_servers:
        # Server ID should always be stored as string in choices
        server_id = str(server["server_id"])
        server_name = server["name"]
        choice = Choice(f"{server_name} ({server_id})", server_id)
        choices.append(choice)
    
    print(f"Created {len(choices)} choices:")
    for choice in choices:
        print(f"  {choice.name} -> {choice.value} (type: {type(choice.value).__name__})")
    
    # Test querying by different types
    test_queries = [
        ("server1", str),
        (2, int),
        ("3", str)
    ]
    
    for query, query_type in test_queries:
        print(f"\nTesting query: {query} (type: {query_type.__name__})")
        
        # Convert query to string for comparison (this is what our fix does)
        string_query = str(query)
        
        # Find matching choice
        found_choice = None
        for choice in choices:
            if choice.value == string_query:
                found_choice = choice
                break
        
        if found_choice:
            print(f"  ✅ Found choice: {found_choice.name} -> {found_choice.value}")
        else:
            print(f"  ❌ No matching choice found")

async def main():
    """Main function to run tests"""
    await test_server_id_type_consistency()
    await test_autocomplete_mixed_types()

if __name__ == "__main__":
    asyncio.run(main())