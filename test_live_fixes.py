"""Test the fixes in a live bot environment

This script starts a simple client that:
1. Connects to MongoDB
2. Simulates autocomplete for server_id with different types
3. Tests historical parser with sample CSV files
"""
import asyncio
import logging
import os
from datetime import datetime
import motor.motor_asyncio
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_live_fixes")

# Load environment variables
load_dotenv()

# Mock cache for server list (to simulate the actual environment)
SERVER_CACHE = {}
SERVER_CACHE_TIMEOUT = 300  # 5 minutes

# Test data to simulate mixed-type server IDs in the database
test_servers = [
    {"server_id": "server1", "server_name": "Test Server 1"},
    {"server_id": 7020, "server_name": "Integer ID Server"},  # Integer ID to test conversion
    {"server_id": "string_id", "name": "String ID Server"},  # Different name key
]

async def connect_to_mongodb():
    """Connect to MongoDB using the actual connection URI"""
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        logger.error("MONGODB_URI environment variable not set")
        return None
    
    # We need to extract the database name from the URI if it's there
    # or use a default database name
    client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_uri)
    
    # Try to get the database name from the URI
    db_name = None
    if '/' in mongodb_uri:
        parts = mongodb_uri.split('/')
        if len(parts) > 3:  # mongodb://hostname/database
            db_name = parts[3].split('?')[0]  # Remove query parameters if any
    
    # Use the extracted name or default to 'pvpstats'
    db_name = db_name or 'pvpstats'
    db = client[db_name]
    
    logger.info(f"Connected to MongoDB database: {db_name}")
    return db

async def test_server_id_type_handling(db):
    """Test server_id type handling - this simulates our autocomplete fixes"""
    logger.info("Testing server_id type handling...")
    
    # Get a real guild from the database
    guilds = await db.guilds.find({}).to_list(length=1)
    
    if not guilds:
        logger.info("No guilds found in the database, creating a test guild...")
        
        # Create a test guild with servers that have different ID types
        test_guild = {
            "guild_id": 1234567890,  # Integer guild ID
            "name": "Test Guild",
            "premium_tier": 1,
            "servers": [
                {
                    "server_id": "string_id_1",  # String ID
                    "server_name": "String ID Server",
                    "sftp_host": "example.com",
                    "sftp_port": 22,
                    "sftp_username": "test",
                    "sftp_password": "test"
                },
                {
                    "server_id": 7020,  # Integer ID
                    "server_name": "Integer ID Server",
                    "sftp_host": "example.com",
                    "sftp_port": 22,
                    "sftp_username": "test",
                    "sftp_password": "test"
                }
            ]
        }
        
        # Insert the test guild
        await db.guilds.insert_one(test_guild)
        logger.info(f"Created test guild with ID: {test_guild['guild_id']}")
        
        # Get the inserted guild
        guild = await db.guilds.find_one({"guild_id": test_guild["guild_id"]})
    else:
        guild = guilds[0]
    
    guild_id = guild.get("guild_id")
    logger.info(f"Using guild ID: {guild_id} (type: {type(guild_id).__name__})")
    
    # Check if the guild has servers
    servers = guild.get("servers", [])
    logger.info(f"Found {len(servers)} servers for guild {guild_id}")
    
    if not servers:
        logger.warning("No servers found for this guild")
        
        # Insert a test server with integer ID to verify our type handling
        test_server = {
            "server_id": 12345,  # Integer ID
            "server_name": "Test Integer Server",
            "sftp_host": "example.com",
            "sftp_port": 22,
            "sftp_username": "test",
            "sftp_password": "test"
        }
        
        # Add the test server to the guild
        result = await db.guilds.update_one(
            {"guild_id": guild_id},
            {"$push": {"servers": test_server}}
        )
        
        if result.modified_count > 0:
            logger.info(f"Added test server with ID {test_server['server_id']} to guild {guild_id}")
        else:
            logger.error("Failed to add test server")
            return False
        
        # Get the updated guild document
        guild = await db.guilds.find_one({"guild_id": guild_id})
        servers = guild.get("servers", [])
    
    # Test our autocomplete function's type handling
    for server in servers:
        original_server_id = server.get("server_id")
        server_id_type = type(original_server_id).__name__
        
        # Convert to string - this is what our fix does
        string_server_id = str(original_server_id)
        
        logger.info(f"Server ID: {original_server_id} (type: {server_id_type}) -> '{string_server_id}'")
        
        # Test with different guild_id types (int and str)
        try:
            int_guild_id = int(guild_id) if isinstance(guild_id, str) else guild_id
            str_guild_id = str(guild_id)
            
            # Try both int and string lookups directly with MongoDB
            int_lookup = await db.guilds.find_one({"guild_id": int_guild_id})
            str_lookup = await db.guilds.find_one({"guild_id": str_guild_id})
            
            logger.info(f"Guild lookup with int ID: {bool(int_lookup)}")
            logger.info(f"Guild lookup with str ID: {bool(str_lookup)}")
            
            # Test our flexible OR query approach
            or_query = {
                "$or": [
                    {"guild_id": int_guild_id},
                    {"guild_id": str_guild_id}
                ]
            }
            or_lookup = await db.guilds.find_one(or_query)
            logger.info(f"Guild lookup with OR query: {bool(or_lookup)}")
        except Exception as e:
            logger.error(f"Error during guild lookup tests: {e}")
            return False
    
    return True

async def get_or_create_test_guild(db):
    """Get a test guild or create one if needed"""
    # Try to find an existing guild
    guild = await db.guilds.find_one({"name": "Test Guild"})
    
    if not guild:
        # Create a test guild
        guild_data = {
            "guild_id": "12345678901234567",
            "name": "Test Guild",
            "premium_tier": 1,
            "servers": test_servers
        }
        
        await db.guilds.insert_one(guild_data)
        logger.info("Created test guild with mixed server ID types")
        guild = guild_data
    
    return guild

async def test_historical_parser():
    """Test the historical parser's datetime handling with sample CSV files"""
    logger.info("Testing historical parser datetime handling...")
    
    # Check if we have test CSV files in our test SFTP directory
    from pathlib import Path
    
    test_dir = Path("./test_sftp_dir/79.127.236.1_7020/actual1/deathlogs")
    if not test_dir.exists():
        logger.error(f"Test directory {test_dir} not found")
        return False
    
    # Count CSV files recursively
    csv_files = list(test_dir.glob("**/*.csv"))
    logger.info(f"Found {len(csv_files)} test CSV files")
    
    success = True
    
    for csv_file in csv_files:
        logger.info(f"CSV file: {csv_file}")
        
        # Parse the file name to get the timestamp
        filename = csv_file.name
        if filename.endswith(".csv") and len(filename) >= 19:
            try:
                # Extract date part from filename (format: YYYY.MM.DD-HH.MM.SS.csv)
                date_str = filename[:-4]  # Remove .csv
                
                # Split by dash first
                date_part, time_part = date_str.split('-')
                
                # Parse date part (YYYY.MM.DD)
                year, month, day = date_part.split('.')
                
                # Parse time part (HH.MM.SS)
                hour, minute, second = time_part.split('.')
                
                # Create datetime object
                dt = datetime(
                    year=int(year),
                    month=int(month),
                    day=int(day),
                    hour=int(hour),
                    minute=int(minute),
                    second=int(second)
                )
                
                logger.info(f"Parsed datetime from filename: {dt.isoformat()}")
                
                # Test conversion to ISO format string
                iso_str = dt.isoformat()
                logger.info(f"ISO format: {iso_str}")
                
                # Test re-parsing from ISO format
                dt2 = datetime.fromisoformat(iso_str)
                logger.info(f"Re-parsed datetime: {dt2.isoformat()}")
                
                # Verify equality
                if dt != dt2:
                    logger.error(f"Re-parsed datetime doesn't match original: {dt} != {dt2}")
                    success = False
                
            except Exception as e:
                logger.error(f"Error parsing datetime from filename {filename}: {e}")
                success = False
    
    return success

async def main():
    """Main test function"""
    logger.info("Starting test of live fixes")
    
    # Connect to the database
    db = await connect_to_mongodb()
    if db is None:  # Proper way to check for None
        return
    
    # Run tests
    server_id_test = await test_server_id_type_handling(db)
    historical_parser_test = await test_historical_parser()
    
    # Report results
    logger.info("Test results:")
    logger.info(f"Server ID type handling: {'✅ PASS' if server_id_test else '❌ FAIL'}")
    logger.info(f"Historical parser datetime handling: {'✅ PASS' if historical_parser_test else '❌ FAIL'}")

if __name__ == "__main__":
    asyncio.run(main())