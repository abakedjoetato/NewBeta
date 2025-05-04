"""
Setup script for Bounty System in Tower of Temptation PvP Statistics Discord Bot.

This script ensures:
1. The 'bounties' collection exists in MongoDB
2. Proper indexes are created for efficient querying
3. Existing data types are validated and fixed if needed

Run this script before using the bounty system for the first time.
"""
import asyncio
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import database utilities
from utils.database import get_db
from config import COLLECTIONS

async def setup_bounty_collection():
    """Set up the bounties collection and its indexes"""
    try:
        db = await get_db()
        
        # Make sure the bounties collection is in config.COLLECTIONS
        if "bounties" not in COLLECTIONS:
            logger.warning("'bounties' not found in COLLECTIONS config! Adding it to local config.")
            COLLECTIONS["bounties"] = "bounties"
        
        # Get or create the bounties collection
        if "bounties" not in await db.list_collection_names():
            logger.info("Creating bounties collection...")
            await db.create_collection("bounties")
            logger.info("Bounties collection created successfully!")
        else:
            logger.info("Bounties collection already exists.")
        
        # Get the collection reference
        bounties = db.get_collection("bounties")
        
        # Create indexes for efficient querying
        logger.info("Creating indexes for bounties collection...")
        
        # Index for querying active bounties by guild and server
        await bounties.create_index([
            ("guild_id", 1),
            ("server_id", 1),
            ("status", 1),
            ("expires_at", 1)
        ], background=True)
        
        # Index for querying bounties by target
        await bounties.create_index([
            ("guild_id", 1),
            ("server_id", 1),
            ("target_id", 1),
            ("status", 1)
        ], background=True)
        
        # Index for querying bounties by placer
        await bounties.create_index([
            ("guild_id", 1),
            ("server_id", 1),
            ("placed_by", 1)
        ], background=True)
        
        # Index for querying bounties by claimer
        await bounties.create_index([
            ("guild_id", 1),
            ("server_id", 1),
            ("claimed_by", 1),
            ("status", 1)
        ], background=True)
        
        # TTL index to automatically remove very old bounties (30 days)
        # Note: This is different from expiring bounties, which just changes their status
        await bounties.create_index(
            "placed_at", 
            expireAfterSeconds=30 * 24 * 60 * 60,  # 30 days
            background=True
        )
        
        logger.info("All indexes created successfully!")
        
        # Validate existing data
        await validate_existing_bounties(db)
        
        return True
    except Exception as e:
        logger.error(f"Error setting up bounty collection: {e}", exc_info=True)
        return False

async def validate_existing_bounties(db):
    """Validate existing bounty data and fix any issues"""
    try:
        # Get the bounties collection
        bounties = db.get_collection("bounties")
        
        # Count documents
        count = await bounties.count_documents({})
        logger.info(f"Found {count} existing bounty documents")
        
        if count == 0:
            logger.info("No existing bounties to validate")
            return
        
        # Validate status field
        logger.info("Validating status field...")
        invalid_status = await bounties.count_documents({
            "status": {"$nin": ["active", "claimed", "expired"]}
        })
        
        if invalid_status > 0:
            logger.warning(f"Found {invalid_status} bounties with invalid status")
            await bounties.update_many(
                {"status": {"$nin": ["active", "claimed", "expired"]}},
                {"$set": {"status": "expired"}}
            )
            logger.info("Fixed invalid status fields")
        
        # Fix missing expires_at field
        logger.info("Checking for missing expires_at field...")
        missing_expires = await bounties.count_documents({
            "status": "active",
            "expires_at": {"$exists": False}
        })
        
        if missing_expires > 0:
            logger.warning(f"Found {missing_expires} active bounties without expires_at field")
            now = datetime.utcnow()
            one_hour = timedelta(hours=1)
            
            # Update documents in batches
            cursor = bounties.find({
                "status": "active",
                "expires_at": {"$exists": False}
            })
            
            batch_size = 100
            batch = []
            async for doc in cursor:
                # Calculate expiration time based on placed_at
                placed_at = doc.get("placed_at", now)
                if isinstance(placed_at, str):
                    try:
                        placed_at = datetime.fromisoformat(placed_at.replace("Z", "+00:00"))
                    except ValueError:
                        placed_at = now
                
                expires_at = placed_at + one_hour
                
                # If it would already be expired, set status to expired
                if expires_at < now:
                    update = {
                        "expires_at": expires_at,
                        "status": "expired"
                    }
                else:
                    update = {"expires_at": expires_at}
                
                batch.append({
                    "filter": {"_id": doc["_id"]},
                    "update": {"$set": update}
                })
                
                if len(batch) >= batch_size:
                    # Execute batch update
                    operations = [{"updateOne": item} for item in batch]
                    await bounties.bulk_write(operations)
                    batch = []
            
            # Process any remaining documents
            if batch:
                operations = [{"updateOne": item} for item in batch]
                await bounties.bulk_write(operations)
            
            logger.info("Fixed all missing expires_at fields")
        
        # Check for old active bounties that should be expired
        logger.info("Checking for outdated active bounties...")
        now = datetime.utcnow()
        outdated = await bounties.count_documents({
            "status": "active",
            "expires_at": {"$lt": now}
        })
        
        if outdated > 0:
            logger.warning(f"Found {outdated} active bounties that should be expired")
            result = await bounties.update_many(
                {
                    "status": "active",
                    "expires_at": {"$lt": now}
                },
                {"$set": {"status": "expired"}}
            )
            logger.info(f"Expired {result.modified_count} outdated bounties")
        
        logger.info("Bounty data validation complete!")
    
    except Exception as e:
        logger.error(f"Error validating bounty data: {e}", exc_info=True)

async def setup_guild_auto_bounty_settings():
    """Set up default auto-bounty settings in all guilds"""
    try:
        db = await get_db()
        guilds = db.get_collection("guilds")
        
        # Count guilds without auto_bounty settings
        missing_settings = await guilds.count_documents({
            "premium_tier": {"$gt": 1},  # Only premium tier 2+
            "auto_bounty": {"$exists": False}
        })
        
        if missing_settings == 0:
            logger.info("All premium guilds already have auto_bounty settings")
            return
        
        logger.info(f"Adding default auto_bounty settings to {missing_settings} premium guilds")
        
        # Default settings
        default_settings = {
            "enabled": True,
            "min_reward": 100,
            "max_reward": 500,
            "kill_threshold": 5,
            "repeat_threshold": 3,
            "time_window": 10
        }
        
        # Update all premium guilds that don't have auto_bounty settings
        result = await guilds.update_many(
            {
                "premium_tier": {"$gt": 1},
                "auto_bounty": {"$exists": False}
            },
            {"$set": {"auto_bounty": default_settings}}
        )
        
        logger.info(f"Added default auto_bounty settings to {result.modified_count} guilds")
    
    except Exception as e:
        logger.error(f"Error setting up guild auto-bounty settings: {e}", exc_info=True)

async def check_server_config_for_bounty_channel():
    """Check if servers have bounty_channel configured and add to DB schema if needed"""
    try:
        db = await get_db()
        guilds = db.get_collection("guilds")
        
        # Add bounty_channel field to guild schema if not already present
        # This is a no-op if the field already exists
        logger.info("Checking for bounty_channel in guild configuration...")
        
        # Count guilds with premium tier 2+ but no bounty_channel
        missing_channel = await guilds.count_documents({
            "premium_tier": {"$gt": 1},
            "bounty_channel": {"$exists": False}
        })
        
        if missing_channel > 0:
            logger.info(f"Found {missing_channel} premium guilds without bounty_channel configuration")
            result = await guilds.update_many(
                {
                    "premium_tier": {"$gt": 1},
                    "bounty_channel": {"$exists": False}
                },
                {"$set": {"bounty_channel": None}}
            )
            logger.info(f"Added bounty_channel field to {result.modified_count} guilds")
    
    except Exception as e:
        logger.error(f"Error checking server config for bounty channel: {e}", exc_info=True)

async def main():
    """Main function to run all setup tasks"""
    logger.info("Starting Bounty System setup...")
    
    # Setup bounties collection and indexes
    success = await setup_bounty_collection()
    if not success:
        logger.error("Failed to set up bounty collection")
        return
    
    # Setup auto-bounty settings in guilds
    await setup_guild_auto_bounty_settings()
    
    # Check for bounty channel configuration
    await check_server_config_for_bounty_channel()
    
    logger.info("Bounty System setup completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())