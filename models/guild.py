"""
Guild model for Tower of Temptation PvP Statistics Bot

This module defines the Guild data structure for Discord guilds.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, ClassVar, List
import uuid

from models.base_model import BaseModel

logger = logging.getLogger(__name__)

class Guild(BaseModel):
    """Discord guild configuration"""
    collection_name: ClassVar[str] = "guilds"
    
    def __init__(
        self,
        guild_id: Optional[str] = None,
        name: Optional[str] = None,
        premium_tier: int = 0,
        admin_role_id: Optional[str] = None,
        admin_users: Optional[List[str]] = None,
        color_primary: str = "#7289DA",
        color_secondary: str = "#FFFFFF",
        color_accent: str = "#23272A",
        icon_url: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        **kwargs
    ):
        self._id = None
        self.guild_id = guild_id
        self.name = name
        self.premium_tier = premium_tier
        self.admin_role_id = admin_role_id
        self.admin_users = admin_users or []
        self.color_primary = color_primary
        self.color_secondary = color_secondary
        self.color_accent = color_accent
        self.icon_url = icon_url
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        
        # Add any additional guild attributes
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    async def get_by_guild_id(cls, db, guild_id: str) -> Optional['Guild']:
        """Get a guild by guild_id
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
            
        Returns:
            Guild object or None if not found
        """
        document = await db.guilds.find_one({"guild_id": guild_id})
        return cls.from_document(document) if document else None
    
    async def set_premium_tier(self, db, tier: int) -> bool:
        """Set premium tier for guild
        
        Args:
            db: Database connection
            tier: Premium tier (0-3)
            
        Returns:
            True if updated successfully, False otherwise
        """
        if tier < 0 or tier > 3:
            return False
            
        self.premium_tier = tier
        self.updated_at = datetime.utcnow()
        
        # Update in database
        result = await db.guilds.update_one(
            {"guild_id": self.guild_id},
            {"$set": {
                "premium_tier": self.premium_tier,
                "updated_at": self.updated_at
            }}
        )
        
        return result.modified_count > 0
    
    async def set_admin_role(self, db, role_id: str) -> bool:
        """Set admin role for guild
        
        Args:
            db: Database connection
            role_id: Discord role ID
            
        Returns:
            True if updated successfully, False otherwise
        """
        self.admin_role_id = role_id
        self.updated_at = datetime.utcnow()
        
        # Update in database
        result = await db.guilds.update_one(
            {"guild_id": self.guild_id},
            {"$set": {
                "admin_role_id": self.admin_role_id,
                "updated_at": self.updated_at
            }}
        )
        
        return result.modified_count > 0
    
    async def add_admin_user(self, db, user_id: str) -> bool:
        """Add admin user for guild
        
        Args:
            db: Database connection
            user_id: Discord user ID
            
        Returns:
            True if updated successfully, False otherwise
        """
        if not hasattr(self, "admin_users"):
            self.admin_users = []
            
        if user_id in self.admin_users:
            return True
            
        self.admin_users.append(user_id)
        self.updated_at = datetime.utcnow()
        
        # Update in database
        result = await db.guilds.update_one(
            {"guild_id": self.guild_id},
            {"$set": {
                "admin_users": self.admin_users,
                "updated_at": self.updated_at
            }}
        )
        
        return result.modified_count > 0
    
    async def remove_admin_user(self, db, user_id: str) -> bool:
        """Remove admin user for guild
        
        Args:
            db: Database connection
            user_id: Discord user ID
            
        Returns:
            True if updated successfully, False otherwise
        """
        if not hasattr(self, "admin_users") or user_id not in self.admin_users:
            return True
            
        self.admin_users.remove(user_id)
        self.updated_at = datetime.utcnow()
        
        # Update in database
        result = await db.guilds.update_one(
            {"guild_id": self.guild_id},
            {"$set": {
                "admin_users": self.admin_users,
                "updated_at": self.updated_at
            }}
        )
        
        return result.modified_count > 0
    
    async def update_theme(self, db, color_primary: Optional[str] = None, color_secondary: Optional[str] = None, color_accent: Optional[str] = None, icon_url: Optional[str] = None) -> bool:
        """Update theme colors for guild
        
        Args:
            db: Database connection
            color_primary: Primary color (hex)
            color_secondary: Secondary color (hex)
            color_accent: Accent color (hex)
            icon_url: Icon URL
            
        Returns:
            True if updated successfully, False otherwise
        """
        update_dict = {"updated_at": datetime.utcnow()}
        
        if color_primary is not None:
            self.color_primary = color_primary
            update_dict["color_primary"] = color_primary
        
        if color_secondary is not None:
            self.color_secondary = color_secondary
            update_dict["color_secondary"] = color_secondary
        
        if color_accent is not None:
            self.color_accent = color_accent
            update_dict["color_accent"] = color_accent
        
        if icon_url is not None:
            self.icon_url = icon_url
            update_dict["icon_url"] = icon_url
        
        self.updated_at = update_dict["updated_at"]
        
        # Update in database
        result = await db.guilds.update_one(
            {"guild_id": self.guild_id},
            {"$set": update_dict}
        )
        
        return result.modified_count > 0