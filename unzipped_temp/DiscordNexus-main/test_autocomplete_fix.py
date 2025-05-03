"""Test the server_id_autocomplete fix for historical parsing

This script mimics the environment for testing the autocomplete fixes we've implemented
for consistent server ID type handling in autocomplete functions.
"""
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_autocomplete")

# Simulated cache for server list to mimic the actual setup
SERVER_CACHE = {}
SERVER_CACHE_TIMEOUT = 300  # 5 minutes

# Test data
test_servers = [
    {"server_id": "server1", "server_name": "Test Server 1"},
    {"server_id": 2, "server_name": "Test Server 2"},  # Integer ID to test conversion
    {"server_id": "server3", "name": "Test Server 3"},  # Different name key
]

# Simulated MongoDB database client
class MockDB:
    async def find_one(self, query):
        guild_id = query.get("guild_id")
        if guild_id:
            return {
                "guild_id": guild_id,
                "name": f"Test Guild {guild_id}",
                "servers": test_servers
            }
        return None

# Simulated Discord objects
class MockInteraction:
    def __init__(self, command_name, guild_id=123456789, options=None, current=""):
        self.guild_id = guild_id
        self.current = current
        self.data = {
            "name": command_name,
            "options": options or []
        }
        self.client = MockBot()

class MockBot:
    def __init__(self):
        self.db = MockDB()
        
    def get_cog(self, name):
        return MockCog() if name == "Setup" else None

class MockCog:
    def __init__(self):
        self.bot = MockBot()

class Choice:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        
    def __str__(self):
        return f"Choice(name='{self.name}', value='{self.value}')"

# Mock app_commands namespace
class app_commands:
    @staticmethod
    def Choice(name, value):
        return Choice(name, value)

async def server_id_autocomplete(interaction, current):
    """Autocomplete for server selection by name, returns server_id as value"""
    try:
        # Enhanced logging for debugging
        command_info = {}
        
        # Extract the full command path and options data
        command_info["command_name"] = interaction.data.get("name", "unknown")
        command_info["focused_option"] = interaction.data.get("focused", "unknown")
        command_info["options_data"] = []
        
        # Get detailed information about the command structure
        if "options" in interaction.data:
            # Log all options data
            options = interaction.data["options"]
            for option in options:
                option_data = {
                    "name": option.get("name", "unknown"),
                    "type": option.get("type", "unknown"),
                    "focused": option.get("focused", False)
                }
                
                # If this option has suboptions (like a subcommand), extract those
                if "options" in option:
                    option_data["sub_options"] = []
                    for sub_option in option["options"]:
                        sub_option_data = {
                            "name": sub_option.get("name", "unknown"),
                            "type": sub_option.get("type", "unknown"),
                            "focused": sub_option.get("focused", False)
                        }
                        option_data["sub_options"].append(sub_option_data)
                        
                command_info["options_data"].append(option_data)
        
        # Determine which subcommand we're in
        subcommand_detected = None
        if command_info["options_data"] and len(command_info["options_data"]) > 0:
            first_option = command_info["options_data"][0]
            if isinstance(first_option, dict):
                subcommand_detected = first_option.get("name")
        
        # These commands always need fresh data from the database
        force_fresh_data = subcommand_detected in ["historicalparse", "diagnose", "removeserver", "setupchannels"]
        
        # Log the detection information
        logger.info(f"Detected subcommand: {subcommand_detected}, forcing fresh data: {force_fresh_data}")
        
        # Get user's guild ID
        guild_id = interaction.guild_id
        
        # Get server data (either cached or fresh)
        cog = interaction.client.get_cog("Setup")
        if not cog:
            # Fall back to a simple fetch if cog not available
            bot = interaction.client

            # Use timeout protection for database operation
            try:
                guild_data = await bot.db.find_one({"guild_id": guild_id})
                servers = []

                if guild_data and "servers" in guild_data:
                    # Get server data
                    servers = guild_data["servers"]

                    # Ensure all server_ids are strings
                    for server in servers:
                        if "server_id" in server:
                            server["server_id"] = str(server["server_id"])
            except Exception as e:
                logger.error(f"Error fetching guild data in autocomplete: {e}")
                servers = []
        else:
            # Try to get data from cache first (unless we're forcing fresh data)
            cache_key = f"servers_{guild_id}"
            cached_data = None if force_fresh_data else SERVER_CACHE.get(cache_key)
            
            use_cache = (not force_fresh_data and 
                         cached_data and 
                         (datetime.now() - cached_data["timestamp"]).total_seconds() < SERVER_CACHE_TIMEOUT)

            if use_cache:
                # Use cached data if it's still valid
                servers = cached_data["servers"]
                logger.info(f"Using cached server data for guild {guild_id}: {len(servers)} servers")
            else:
                # Fetch fresh data and update cache with timeout protection
                try:
                    # Log why we're fetching fresh data
                    if force_fresh_data:
                        logger.info(f"Fetching fresh server data for subcommand {subcommand_detected}")
                    elif not cached_data:
                        logger.info("No cached data available, fetching fresh data")
                    else:
                        logger.info("Cache expired, fetching fresh data")
                    
                    guild_data = await cog.bot.db.find_one({"guild_id": guild_id})
                    servers = []

                    if guild_data and "servers" in guild_data:
                        # Get server data
                        servers = guild_data["servers"]
                        logger.info(f"Found {len(servers)} servers in fresh database query")

                    # Ensure all server_ids are strings
                    for server in servers:
                        if "server_id" in server:
                            old_id = server["server_id"]
                            server["server_id"] = str(server["server_id"])
                            if old_id != server["server_id"]:
                                logger.info(f"Converted server_id from {type(old_id).__name__} to string: {old_id} -> {server['server_id']}")
                    
                    # Update cache (even for forced fresh data - this keeps it fresh for next time)
                    SERVER_CACHE[cache_key] = {
                        "timestamp": datetime.now(),
                        "servers": servers
                    }
                    logger.info(f"Updated cache for guild {guild_id} with {len(servers)} servers")
                except Exception as e:
                    logger.error(f"Error refreshing guild data in autocomplete: {e}")
                    servers = []

        # Filter servers based on current input
        choices = []
        for server in servers:
            # Always ensure server_id is a string for consistent comparison
            raw_server_id = server.get("server_id", "")
            server_id = str(raw_server_id) if raw_server_id is not None else ""

            # Log the type conversions for debugging
            logger.info(f"Autocomplete converting server_id from {type(raw_server_id).__name__} to string: {server_id}")

            # Get proper server name, check both keys: 'name' and 'server_name'
            server_name = server.get("server_name", server.get("name", "Unknown"))

            # Make sure we have a valid display name
            if server_name == "Unknown" and server_id:
                server_name = f"Server {server_id}"

            # Check if current input matches server name or ID
            # For empty input (very important for auto-complete), show all options
            # For non-empty input, filter by server name or ID
            if not current or current.lower() in server_name.lower() or current.lower() in server_id.lower():
                # Format: "ServerName (ServerID)"
                choices.append(app_commands.Choice(
                    name=f"{server_name} ({server_id})",
                    value=server_id  # Ensure this is a string
                ))

        return choices[:25]  # Discord has a limit of 25 choices

    except Exception as e:
        logger.error(f"Error in server_id_autocomplete: {e}")
        return []

async def test_autocomplete():
    """Test autocomplete function with different command types and input values"""
    
    # Test 1: Empty current, normal command
    interaction = MockInteraction("setup", options=[])
    choices = await server_id_autocomplete(interaction, "")
    logger.info(f"Test 1 - Empty current, normal command: {len(choices)} choices returned")
    for choice in choices:
        logger.info(f"  - {choice}")
    
    # Test 2: With current input that matches server name
    interaction = MockInteraction("setup", options=[])
    choices = await server_id_autocomplete(interaction, "test")
    logger.info(f"Test 2 - With matching input 'test': {len(choices)} choices returned")
    for choice in choices:
        logger.info(f"  - {choice}")

    # Test 3: With historicalparse subcommand
    interaction = MockInteraction("setup", options=[{"name": "historicalparse", "type": 1}])
    choices = await server_id_autocomplete(interaction, "")
    logger.info(f"Test 3 - Historical parse command: {len(choices)} choices returned")
    for choice in choices:
        logger.info(f"  - {choice}")
    
    # Test 4: Integer server ID should be converted to string
    # In our test_servers, we have one with an integer ID = 2
    logger.info("Test 4 - Verifying integer server ID is converted to string")
    for choice in choices:
        if "Test Server 2" in choice.name:
            logger.info(f"  - Server 2 choice: {choice} (expected value type: {type(choice.value).__name__})")
    
    # Test 5: Server name property fallback
    logger.info("Test 5 - Verifying name property is used if server_name is not present")
    for choice in choices:
        if "Test Server 3" in choice.name:
            logger.info(f"  - Server 3 choice: {choice}")

async def main():
    logger.info("Starting autocomplete fix test")
    await test_autocomplete()
    logger.info("Test completed")

if __name__ == "__main__":
    asyncio.run(main())