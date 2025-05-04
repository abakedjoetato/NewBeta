"""
Economy model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides an Economy class to interact with economy data in MongoDB.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

class Economy:
    """
    Economy model for in-game currency management
    """
    
    @staticmethod
    async def get_balance(db, discord_id: str, guild_id: str) -> int:
        """
        Get a player's currency balance
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            Current balance (0 if not found)
        """
        economy_data = await db.db.economy.find_one({
            "discord_id": discord_id,
            "guild_id": guild_id
        })
        
        if not economy_data:
            # Create new economy record
            economy_data = {
                "discord_id": discord_id,
                "guild_id": guild_id,
                "balance": 0,
                "last_updated": datetime.utcnow()
            }
            await db.db.economy.insert_one(economy_data)
            
        return economy_data.get("balance", 0)
    
    @staticmethod
    async def add_currency(db, discord_id: str, guild_id: str, amount: int, 
                         description: Optional[str] = None, 
                         transaction_type: str = "other") -> bool:
        """
        Add currency to a player's balance
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Discord guild ID
            amount: Amount to add
            description: Transaction description
            transaction_type: Type of transaction
            
        Returns:
            True if successful, False otherwise
        """
        if amount <= 0:
            return False
            
        # Update player's balance
        result = await db.db.economy.update_one(
            {"discord_id": discord_id, "guild_id": guild_id},
            {
                "$inc": {"balance": amount},
                "$set": {"last_updated": datetime.utcnow()}
            },
            upsert=True
        )
        
        # Record transaction
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
    
    @staticmethod
    async def remove_currency(db, discord_id: str, guild_id: str, amount: int, 
                            description: Optional[str] = None, 
                            transaction_type: str = "other") -> bool:
        """
        Remove currency from a player's balance
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Discord guild ID
            amount: Amount to remove
            description: Transaction description
            transaction_type: Type of transaction
            
        Returns:
            True if successful, False if insufficient funds
        """
        if amount <= 0:
            return False
            
        # Get current balance
        balance = await Economy.get_balance(db, discord_id, guild_id)
        
        # Check if player has enough
        if balance < amount:
            return False
            
        # Update player's balance
        result = await db.db.economy.update_one(
            {"discord_id": discord_id, "guild_id": guild_id},
            {
                "$inc": {"balance": -amount},
                "$set": {"last_updated": datetime.utcnow()}
            }
        )
        
        # Record transaction
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
    
    @staticmethod
    async def get_transactions(db, discord_id: str, guild_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get a player's recent transactions
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Discord guild ID
            limit: Maximum number of transactions to return
            
        Returns:
            List of transaction dictionaries
        """
        cursor = db.db.economy_transactions.find({
            "discord_id": discord_id,
            "guild_id": guild_id
        }).sort("timestamp", -1).limit(limit)
        
        return await cursor.to_list(length=limit)