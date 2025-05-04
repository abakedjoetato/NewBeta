"""
MongoDB model definitions for the Tower of Temptation PvP Statistics Discord Bot

This module defines the data structures used throughout the application.
These are not SQLAlchemy models but rather document schemas for MongoDB.
"""
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, TypeVar, ClassVar, Type

# Define a type for document dictionaries
Document = Dict[str, Any]
T = TypeVar('T', bound='BaseModel')

logger = logging.getLogger(__name__)

class BaseModel:
    """Base class for all MongoDB document models
    
    This provides common methods for all models.
    """
    # Collection name in MongoDB
    collection_name: ClassVar[str] = ""
    
    @classmethod
    def from_document(cls: Type[T], document: Dict[str, Any]) -> T:
        """Create a model instance from a MongoDB document
        
        Args:
            document: MongoDB document (dictionary)
        
        Returns:
            Instance of the model
        """
        if document is None:
            return None
        
        instance = cls()
        for key, value in document.items():
            setattr(instance, key, value)
            
        # Ensure _id is always available
        if '_id' in document:
            instance._id = document['_id']
            
        return instance
    
    def to_document(self) -> Dict[str, Any]:
        """Convert model instance to MongoDB document
        
        Returns:
            Dictionary suitable for MongoDB storage
        """
        document = {}
        
        # Get all attributes that don't start with underscore
        for key, value in self.__dict__.items():
            if not key.startswith('_') or key == '_id':
                document[key] = value
                
        return document
        
    def __repr__(self) -> str:
        """String representation of the model"""
        name = self.__class__.__name__
        attrs = []
        
        # Add name/id if available
        if hasattr(self, 'name'):
            attrs.append(f"name='{self.name}'")
        if hasattr(self, '_id'):
            attrs.append(f"id={self._id}")
            
        return f"<{name} {' '.join(attrs)}>"


class Guild(BaseModel):
    """Discord Guild (Server) information"""
    collection_name = "guilds"
    
    def __init__(
        self,
        guild_id: str = None,
        name: str = None,
        premium_tier: int = 0,
        join_date: datetime = None,
        last_activity: datetime = None,
        **kwargs
    ):
        self._id = None  # MongoDB ObjectId
        self.guild_id = guild_id
        self.name = name
        self.premium_tier = premium_tier
        self.join_date = join_date or datetime.utcnow()
        self.last_activity = last_activity or datetime.utcnow()
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)
            
    @classmethod
    async def get_by_guild_id(cls, db, guild_id: str) -> 'Guild':
        """Get a guild by Discord guild_id
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
            
        Returns:
            Guild object or None if not found
        """
        document = await db[cls.collection_name].find_one({"guild_id": guild_id})
        return cls.from_document(document)


class GameServer(BaseModel):
    """Game server configuration"""
    collection_name = "game_servers"
    
    def __init__(
        self,
        guild_id: str = None,
        server_id: str = None,
        name: str = None,
        sftp_host: str = None,
        sftp_port: int = 22,
        sftp_username: str = None,
        sftp_password: str = None,
        sftp_directory: str = None,
        active: bool = True,
        created_at: datetime = None,
        last_sync: datetime = None,
        **kwargs
    ):
        self._id = None  # MongoDB ObjectId
        self.guild_id = guild_id
        self.server_id = server_id
        self.name = name
        self.sftp_host = sftp_host
        self.sftp_port = sftp_port
        self.sftp_username = sftp_username
        self.sftp_password = sftp_password
        self.sftp_directory = sftp_directory
        self.active = active
        self.created_at = created_at or datetime.utcnow()
        self.last_sync = last_sync
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


class Player(BaseModel):
    """Player information from game servers"""
    collection_name = "players"
    
    def __init__(
        self,
        server_id: str = None,
        guild_id: str = None,
        player_id: str = None,
        name: str = None,
        kills: int = 0,
        deaths: int = 0,
        kd_ratio: float = 0.0,
        first_seen: datetime = None,
        last_seen: datetime = None,
        **kwargs
    ):
        self._id = None  # MongoDB ObjectId
        self.server_id = server_id
        self.guild_id = guild_id
        self.player_id = player_id
        self.name = name
        self.kills = kills
        self.deaths = deaths
        self.kd_ratio = kd_ratio
        self.first_seen = first_seen or datetime.utcnow()
        self.last_seen = last_seen or datetime.utcnow()
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)
            
    @classmethod
    async def get_by_player_id(cls, db, server_id: str, player_id: str) -> 'Player':
        """Get a player by server_id and player_id
        
        Args:
            db: Database connection
            server_id: Game server ID
            player_id: Player ID in the game
            
        Returns:
            Player object or None if not found
        """
        document = await db[cls.collection_name].find_one({"server_id": server_id, "player_id": player_id})
        return cls.from_document(document)


class PlayerLink(BaseModel):
    """Links between Discord users and in-game players"""
    collection_name = "player_links"
    
    def __init__(
        self,
        discord_id: str = None,
        player_id: str = None,
        server_id: str = None,
        guild_id: str = None,
        verified: bool = False,
        linked_at: datetime = None,
        **kwargs
    ):
        self._id = None  # MongoDB ObjectId
        self.discord_id = discord_id
        self.player_id = player_id
        self.server_id = server_id
        self.guild_id = guild_id
        self.verified = verified
        self.linked_at = linked_at or datetime.utcnow()
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


class Bounty(BaseModel):

    # SOURCE_PLAYER constant
    SOURCE_PLAYER = "player"
    # SOURCE_AUTO constant
    SOURCE_AUTO = "auto"
    # SOURCE_ADMIN constant
    SOURCE_ADMIN = "admin"
    # STATUS_ACTIVE constant
    STATUS_ACTIVE = "active"
    # STATUS_CLAIMED constant
    STATUS_CLAIMED = "claimed"
    # STATUS_EXPIRED constant
    STATUS_EXPIRED = "expired"
    # STATUS_CANCELLED constant
    STATUS_CANCELLED = "cancelled"

    """Bounty information"""
    collection_name = "bounties"
    
    # Bounty source constants
    SOURCE_PLAYER = "player"
    SOURCE_AUTO = "auto"
    SOURCE_ADMIN = "admin"
    
    # Status constants
    STATUS_ACTIVE = "active"
    STATUS_CLAIMED = "claimed"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"
    
    @classmethod
    async def create(cls, db, guild_id: str, server_id: str, target_id: str, 
                     target_name: str, placed_by: str, placed_by_name: str, 
                     reason: str = None, reward: int = 100, source: str = "player",
                     lifespan_hours: float = 1.0) -> Optional['Bounty']:
        """Create a new bounty
        
        Args:
            db: Database connection
            guild_id: Guild ID
            server_id: Server ID
            target_id: Target player ID
            target_name: Target player name
            placed_by: Discord ID of placer
            placed_by_name: Discord name of placer
            reason: Reason for bounty
            reward: Bounty reward amount
            source: Bounty source (player, auto, admin)
            lifespan_hours: Bounty lifespan in hours
            
        Returns:
            Bounty object or None if creation failed
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=lifespan_hours)
        
        # Create bounty
        bounty = cls(
            guild_id=guild_id,
            server_id=server_id,
            target_id=target_id,
            target_name=target_name,
            placed_by=placed_by,
            placed_by_name=placed_by_name,
            reason=reason,
            reward=reward,
            status=cls.STATUS_ACTIVE,
            source=source,
            created_at=now,
            expires_at=expires_at
        )
        
        # Insert into database
        try:
            result = await db[cls.collection_name].insert_one(bounty.to_document())
            bounty._id = result.inserted_id
            return bounty
        except Exception as e:
            logger.error(f"Error creating bounty: {e}")
            return None
            
    @classmethod
    async def get_by_id(cls, db, bounty_id: str) -> Optional['Bounty']:
        """Get a bounty by its ID
        
        Args:
            db: Database connection
            bounty_id: Bounty ID
            
        Returns:
            Bounty object or None if not found
        """
        document = await db[cls.collection_name].find_one({"id": bounty_id})
        return cls.from_document(document)
    
    def __init__(
        self,
        guild_id: str = None,
        server_id: str = None,
        target_id: str = None,
        target_name: str = None,
        placed_by: str = None,  # Discord ID
        placed_by_name: str = None,
        reason: str = None,
        reward: int = 0,
        status: str = "active",
        source: str = "player",  # player, auto
        created_at: datetime = None,
        expires_at: datetime = None,
        claimed_by: str = None,  # Discord ID of claimer
        claimed_by_name: str = None,
        claimed_at: datetime = None,
        **kwargs
    ):
        self._id = None  # MongoDB ObjectId
        self.id = kwargs.get("id", str(uuid.uuid4())[:8])  # Short ID for references
        self.id = kwargs.get("id", str(uuid.uuid4())[:8])  # Short ID for references
        self.guild_id = guild_id
        self.server_id = server_id
        self.target_id = target_id
        self.target_name = target_name
        self.placed_by = placed_by
        self.placed_by_name = placed_by_name
        self.reason = reason
        self.reward = reward
        self.status = status
        self.source = source
        self.created_at = created_at or datetime.utcnow()
        
        # Default expiration is 1 hour from creation
        if expires_at is None and created_at is not None:
            self.expires_at = created_at + timedelta(hours=1)
        elif expires_at is None:
            self.expires_at = datetime.utcnow() + timedelta(hours=1)
        else:
            self.expires_at = expires_at
            
        self.claimed_by = claimed_by
        self.claimed_by_name = claimed_by_name
        self.claimed_at = claimed_at
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    async def create(cls, db, guild_id: str, server_id: str, target_id: str, 
                     target_name: str, placed_by: str, placed_by_name: str, 
                     reason: str = None, reward: int = 100, source: str = "player",
                     lifespan_hours: float = 1.0) -> Optional['Bounty']:
        """Create a new bounty
        
        Args:
            db: Database connection
            guild_id: Guild ID
            server_id: Server ID
            target_id: Target player ID
            target_name: Target player name
            placed_by: Discord ID of placer
            placed_by_name: Discord name of placer
            reason: Reason for bounty
            reward: Bounty reward amount
            source: Bounty source (player, auto, admin)
            lifespan_hours: Bounty lifespan in hours
            
        Returns:
            Bounty object or None if creation failed
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=lifespan_hours)
        
        # Create bounty
        bounty = cls(
            guild_id=guild_id,
            server_id=server_id,
            target_id=target_id,
            target_name=target_name,
            placed_by=placed_by,
            placed_by_name=placed_by_name,
            reason=reason,
            reward=reward,
            status=cls.STATUS_ACTIVE,
            source=source,
            created_at=now,
            expires_at=expires_at
        )
        
        # Insert into database
        try:
            result = await db[cls.collection_name].insert_one(bounty.to_document())
            bounty._id = result.inserted_id
            return bounty
        except Exception as e:
            logger.error(f"Error creating bounty: {e}")
            return None
    

    @classmethod
    async def get_by_id(cls, db, bounty_id: str) -> Optional['Bounty']:
        """Get a bounty by its ID
        
        Args:
            db: Database connection
            bounty_id: Bounty ID
            
        Returns:
            Bounty object or None if not found
        """
        document = await db[cls.collection_name].find_one({"id": bounty_id})
        return cls.from_document(document)
    


class Kill(BaseModel):
    """Kill events tracked from game logs"""
    collection_name = "kills"
    
    def __init__(
        self,
        guild_id: str = None,
        server_id: str = None,
        kill_id: str = None,
        timestamp: datetime = None,
        killer_id: str = None,
        killer_name: str = None,
        victim_id: str = None,
        victim_name: str = None,
        weapon: str = None,
        distance: float = None,
        console: str = None,  # XSX, PS5, etc.
        **kwargs
    ):
        self._id = None  # MongoDB ObjectId
        self.guild_id = guild_id
        self.server_id = server_id
        self.kill_id = kill_id
        self.timestamp = timestamp or datetime.utcnow()
        self.killer_id = killer_id
        self.killer_name = killer_name
        self.victim_id = victim_id
        self.victim_name = victim_name
        self.weapon = weapon
        self.distance = distance
        self.console = console
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


class BotStatus(BaseModel):
    """Tracks the Discord bot's status"""
    collection_name = "bot_status"
    
    def __init__(
        self,
        timestamp: datetime = None,
        is_online: bool = False,
        uptime_seconds: int = 0,
        guild_count: int = 0,
        command_count: int = 0,
        error_count: int = 0,
        version: str = "0.1.0",
        **kwargs
    ):
        self._id = None  # MongoDB ObjectId
        self.timestamp = timestamp or datetime.utcnow()
        self.is_online = is_online
        self.uptime_seconds = uptime_seconds
        self.guild_count = guild_count
        self.command_count = command_count
        self.error_count = error_count
        self.version = version
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


class EconomyTransaction(BaseModel):

    # TYPE_BOUNTY_PLACED constant
    TYPE_BOUNTY_PLACED = "bounty_placed"
    # TYPE_BOUNTY_CLAIMED constant
    TYPE_BOUNTY_CLAIMED = "bounty_claimed"
    # TYPE_BOUNTY_EXPIRED constant
    TYPE_BOUNTY_EXPIRED = "bounty_expired"
    # TYPE_BOUNTY_CANCELLED constant
    TYPE_BOUNTY_CANCELLED = "bounty_cancelled"
    # TYPE_ADMIN_ADJUSTMENT constant
    TYPE_ADMIN_ADJUSTMENT = "admin_adjustment"

    """Tracks in-game currency transactions"""
    collection_name = "economy"
    
    # Transaction types
    TYPE_BOUNTY_PLACED = "bounty_placed"
    TYPE_BOUNTY_CLAIMED = "bounty_claimed"
    TYPE_BOUNTY_EXPIRED = "bounty_expired"
    TYPE_BOUNTY_CANCELLED = "bounty_cancelled"
    TYPE_ADMIN_ADJUSTMENT = "admin_adjustment"
    
    def __init__(
        self,
        discord_id: str = None,
        guild_id: str = None,
        server_id: str = None,
        amount: int = 0,
        type: str = None,  # bounty_placed, bounty_claimed, etc.
        timestamp: datetime = None,
        description: str = None,
        **kwargs
    ):
        self._id = None  # MongoDB ObjectId
        self.id = kwargs.get("id", str(uuid.uuid4())[:8])  # Short ID for references
        self.id = kwargs.get("id", str(uuid.uuid4())[:8])  # Short ID for references
        self.discord_id = discord_id
        self.guild_id = guild_id
        self.server_id = server_id
        self.amount = amount
        self.type = type
        self.timestamp = timestamp or datetime.utcnow()
        self.description = description
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    @classmethod
    async def create(cls, db, discord_id: str, guild_id: str, 
                    amount: int, type: str, 
                    server_id: str = None, 
                    description: str = None) -> Optional['EconomyTransaction']:
        """Create a new economy transaction
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Guild ID
            amount: Transaction amount
            type: Transaction type
            server_id: Optional server ID
            description: Optional transaction description
            
        Returns:
            Transaction object or None if creation failed
        """
        # Create transaction
        transaction = cls(
            discord_id=discord_id,
            guild_id=guild_id,
            server_id=server_id,
            amount=amount,
            type=type,
            timestamp=datetime.utcnow(),
            description=description
        )
        
        # Insert into database
        try:
            result = await db[cls.collection_name].insert_one(transaction.to_document())
            transaction._id = result.inserted_id
            return transaction
        except Exception as e:
            logger.error(f"Error creating transaction: {e}")
            return None
    
    @classmethod
    async def get_by_player(cls, db, discord_id: str, guild_id: str = None) -> List['EconomyTransaction']:
        """Get all transactions for a player
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Optional guild ID to filter by
            
        Returns:
            List of transactions
        """
        query = {"discord_id": discord_id}
        if guild_id:
            query["guild_id"] = guild_id
            
        cursor = db[cls.collection_name].find(query).sort("timestamp", -1)
        
        transactions = []
        async for document in cursor:
            transactions.append(cls.from_document(document))
            
        return transactions