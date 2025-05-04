"""
MongoDB models for the Tower of Temptation PvP Statistics Discord Bot

These models define the schema for MongoDB collections used by the bot.
They provide a consistent interface for database operations across the application.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any

# Model classes for MongoDB documents
class Guild:
    """Discord Guild (Server) information"""
    
    @classmethod
    async def create(cls, db, guild_id: str, name: str, premium_tier: int = 0):
        """Create a new guild record"""
        guild_data = {
            "guild_id": guild_id,
            "name": name,
            "premium_tier": premium_tier,
            "join_date": datetime.utcnow(),
            "last_activity": datetime.utcnow()
        }
        result = await db.db.guilds.insert_one(guild_data)
        guild_data["_id"] = result.inserted_id
        return guild_data
    
    @classmethod
    async def get_by_guild_id(cls, db, guild_id: str):
        """Get a guild by its Discord ID"""
        return await db.db.guilds.find_one({"guild_id": guild_id})
    
    @classmethod
    async def update_activity(cls, db, guild_id: str):
        """Update the last activity timestamp for a guild"""
        await db.db.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"last_activity": datetime.utcnow()}}
        )
    
    @classmethod
    async def update_premium_tier(cls, db, guild_id: str, premium_tier: int):
        """Update the premium tier for a guild"""
        await db.db.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"premium_tier": premium_tier}}
        )

class GameServer:
    """Game server configuration"""
    
    @classmethod
    async def create(cls, db, guild_id: str, server_id: str, name: str, 
                    sftp_host: str = None, sftp_port: int = 22, 
                    sftp_username: str = None, sftp_password: str = None, 
                    sftp_directory: str = None):
        """Create a new game server record"""
        server_data = {
            "guild_id": guild_id,
            "server_id": server_id,
            "name": name,
            "sftp_host": sftp_host,
            "sftp_port": sftp_port,
            "sftp_username": sftp_username,
            "sftp_password": sftp_password,
            "sftp_directory": sftp_directory,
            "active": True,
            "created_at": datetime.utcnow(),
            "last_sync": None
        }
        result = await db.db.game_servers.insert_one(server_data)
        server_data["_id"] = result.inserted_id
        return server_data
    
    @classmethod
    async def get_by_server_id(cls, db, guild_id: str, server_id: str):
        """Get a game server by its ID within a guild"""
        return await db.db.game_servers.find_one({
            "guild_id": guild_id,
            "server_id": server_id
        })
    
    @classmethod
    async def get_servers_for_guild(cls, db, guild_id: str):
        """Get all game servers for a guild"""
        cursor = db.db.game_servers.find({"guild_id": guild_id})
        return await cursor.to_list(length=100)
    
    @classmethod
    async def update_last_sync(cls, db, guild_id: str, server_id: str):
        """Update the last sync timestamp for a server"""
        await db.db.game_servers.update_one(
            {"guild_id": guild_id, "server_id": server_id},
            {"$set": {"last_sync": datetime.utcnow()}}
        )

class Player:
    """Player information from game servers"""
    
    @classmethod
    async def create(cls, db, server_id: str, player_id: str, name: str):
        """Create a new player record"""
        player_data = {
            "server_id": server_id,
            "player_id": player_id,
            "name": name,
            "kills": 0,
            "deaths": 0,
            "kd_ratio": 0.0,
            "first_seen": datetime.utcnow(),
            "last_seen": datetime.utcnow(),
            # Rivalry tracking
            "nemesis": None,  # Player killed by most
            "nemesis_name": None,
            "nemesis_kills": 0,
            "prey": None,     # Player most killed
            "prey_name": None,
            "prey_kills": 0
        }
        result = await db.db.players.insert_one(player_data)
        player_data["_id"] = result.inserted_id
        return player_data
    
    @classmethod
    async def get_by_player_id(cls, db, server_id: str, player_id: str):
        """Get a player by their ID within a server"""
        return await db.db.players.find_one({
            "server_id": server_id,
            "player_id": player_id
        })
    
    @classmethod
    async def update_stats(cls, db, server_id: str, player_id: str, kills: int = None, deaths: int = None):
        """Update player kill/death statistics"""
        update = {"last_seen": datetime.utcnow()}
        if kills is not None:
            update["kills"] = kills
        if deaths is not None:
            update["deaths"] = deaths
        
        # Calculate K/D ratio - avoid division by zero
        if kills is not None and deaths is not None:
            # Use at least 1 death to avoid division by zero
            update["kd_ratio"] = kills / max(deaths, 1)
        
        await db.db.players.update_one(
            {"server_id": server_id, "player_id": player_id},
            {"$set": update}
        )
    
    @classmethod
    async def update_rivalry(cls, db, server_id: str, player_id: str, 
                           nemesis: str = None, nemesis_name: str = None, nemesis_kills: int = None,
                           prey: str = None, prey_name: str = None, prey_kills: int = None):
        """Update player rivalry information"""
        update = {}
        if nemesis is not None:
            update["nemesis"] = nemesis
            update["nemesis_name"] = nemesis_name
            update["nemesis_kills"] = nemesis_kills
        
        if prey is not None:
            update["prey"] = prey
            update["prey_name"] = prey_name
            update["prey_kills"] = prey_kills
            
        if update:
            await db.db.players.update_one(
                {"server_id": server_id, "player_id": player_id},
                {"$set": update}
            )

class PlayerLink:
    """Links between Discord users and in-game players"""
    
    @classmethod
    async def create(cls, db, discord_id: str, server_id: str, player_id: str, verified: bool = False):
        """Create a new player link record"""
        link_data = {
            "discord_id": discord_id,
            "server_id": server_id,
            "player_id": player_id,
            "verified": verified,
            "linked_at": datetime.utcnow()
        }
        result = await db.db.player_links.insert_one(link_data)
        link_data["_id"] = result.inserted_id
        return link_data
    
    @classmethod
    async def get_player_links(cls, db, discord_id: str):
        """Get all player links for a Discord user"""
        cursor = db.db.player_links.find({"discord_id": discord_id})
        return await cursor.to_list(length=100)
    
    @classmethod
    async def verify_link(cls, db, discord_id: str, server_id: str, player_id: str):
        """Mark a player link as verified"""
        await db.db.player_links.update_one(
            {"discord_id": discord_id, "server_id": server_id, "player_id": player_id},
            {"$set": {"verified": True}}
        )

class Bounty:
    """Bounty information"""
    
    @classmethod
    async def create(cls, db, guild_id: str, server_id: str, target_id: str, 
                   placed_by: str, placed_by_name: str, reward: int, 
                   reason: str = None, source: str = "player", 
                   expires_in_hours: int = 1):
        """Create a new bounty record"""
        bounty_data = {
            "guild_id": guild_id,
            "server_id": server_id,
            "target_id": target_id,
            "placed_by": placed_by,
            "placed_by_name": placed_by_name,
            "reason": reason,
            "reward": reward,
            "status": "active",
            "source": source,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=expires_in_hours),
            "claimed_by": None,
            "claimed_by_name": None,
            "claimed_at": None
        }
        result = await db.db.bounties.insert_one(bounty_data)
        bounty_data["_id"] = result.inserted_id
        return bounty_data
    
    @classmethod
    async def get_active_bounties(cls, db, guild_id: str, server_id: str = None, target_id: str = None):
        """Get active bounties with optional filters"""
        query = {
            "guild_id": guild_id,
            "status": "active",
            "expires_at": {"$gt": datetime.utcnow()}
        }
        
        if server_id:
            query["server_id"] = server_id
            
        if target_id:
            query["target_id"] = target_id
            
        cursor = db.db.bounties.find(query)
        return await cursor.to_list(length=100)
    
    @classmethod
    async def claim_bounty(cls, db, bounty_id, claimed_by: str, claimed_by_name: str):
        """Mark a bounty as claimed"""
        await db.db.bounties.update_one(
            {"_id": bounty_id},
            {
                "$set": {
                    "status": "claimed",
                    "claimed_by": claimed_by,
                    "claimed_by_name": claimed_by_name,
                    "claimed_at": datetime.utcnow()
                }
            }
        )
    
    @classmethod
    async def expire_bounties(cls, db):
        """Mark expired bounties as expired"""
        await db.db.bounties.update_many(
            {
                "status": "active",
                "expires_at": {"$lte": datetime.utcnow()}
            },
            {
                "$set": {"status": "expired"}
            }
        )

class Kill:
    """Kill events tracked from game logs"""
    
    @classmethod
    async def create(cls, db, guild_id: str, server_id: str, kill_id: str, 
                   timestamp: datetime, killer_id: str, killer_name: str, 
                   victim_id: str, victim_name: str, weapon: str = None, 
                   distance: float = None, console: str = None):
        """Create a new kill event record"""
        kill_data = {
            "guild_id": guild_id,
            "server_id": server_id,
            "kill_id": kill_id,
            "timestamp": timestamp,
            "killer_id": killer_id,
            "killer_name": killer_name,
            "victim_id": victim_id,
            "victim_name": victim_name,
            "weapon": weapon,
            "distance": distance,
            "console": console
        }
        try:
            result = await db.db.kills.insert_one(kill_data)
            kill_data["_id"] = result.inserted_id
            return kill_data
        except Exception:
            # Kill may already exist (duplicate kill_id)
            return None
    
    @classmethod
    async def get_recent_kills(cls, db, guild_id: str, server_id: str = None, limit: int = 100):
        """Get recent kill events with optional server filter"""
        query = {"guild_id": guild_id}
        
        if server_id:
            query["server_id"] = server_id
            
        cursor = db.db.kills.find(query).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

class Economy:
    """In-game economy management"""
    
    @classmethod
    async def get_balance(cls, db, discord_id: str, guild_id: str):
        """Get a player's current balance"""
        user_economy = await db.db.economy.find_one({
            "discord_id": discord_id,
            "guild_id": guild_id
        })
        
        if not user_economy:
            # Create new economy record with default values
            user_economy = {
                "discord_id": discord_id,
                "guild_id": guild_id,
                "balance": 0,
                "last_updated": datetime.utcnow()
            }
            await db.db.economy.insert_one(user_economy)
            
        return user_economy.get("balance", 0)
    
    @classmethod
    async def add_currency(cls, db, discord_id: str, guild_id: str, amount: int, 
                         description: str = None, transaction_type: str = "other"):
        """Add currency to a player's balance"""
        if amount <= 0:
            return False
            
        # Update the player's balance
        result = await db.db.economy.update_one(
            {"discord_id": discord_id, "guild_id": guild_id},
            {
                "$inc": {"balance": amount},
                "$set": {"last_updated": datetime.utcnow()}
            },
            upsert=True
        )
        
        # Record the transaction
        transaction = {
            "discord_id": discord_id,
            "guild_id": guild_id,
            "amount": amount,
            "type": transaction_type,
            "timestamp": datetime.utcnow(),
            "description": description
        }
        await db.db.economy_transactions.insert_one(transaction)
        
        return True
    
    @classmethod
    async def remove_currency(cls, db, discord_id: str, guild_id: str, amount: int, 
                            description: str = None, transaction_type: str = "other"):
        """Remove currency from a player's balance"""
        if amount <= 0:
            return False
            
        # Get current balance
        balance = await cls.get_balance(db, discord_id, guild_id)
        
        # Check if player has enough currency
        if balance < amount:
            return False
            
        # Update the player's balance
        result = await db.db.economy.update_one(
            {"discord_id": discord_id, "guild_id": guild_id},
            {
                "$inc": {"balance": -amount},
                "$set": {"last_updated": datetime.utcnow()}
            }
        )
        
        # Record the transaction
        transaction = {
            "discord_id": discord_id,
            "guild_id": guild_id,
            "amount": -amount,
            "type": transaction_type,
            "timestamp": datetime.utcnow(),
            "description": description
        }
        await db.db.economy_transactions.insert_one(transaction)
        
        return True