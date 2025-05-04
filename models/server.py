"""
Server model for Tower of Temptation PvP Statistics Bot

This module defines the Server data structure for game servers.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, ClassVar, List

from models.base_model import BaseModel

logger = logging.getLogger(__name__)

class Server(BaseModel):
    """Game server data"""
    collection_name: ClassVar[str] = "game_servers"
    
    # Server status constants
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_ERROR = "error"
    STATUS_MAINTENANCE = "maintenance"
    
    def __init__(
        self,
        server_id: Optional[str] = None,
        guild_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: str = STATUS_ACTIVE,
        hostname: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        sftp_directory: Optional[str] = None,
        log_directory: Optional[str] = None,
        last_checked: Optional[datetime] = None,
        last_error: Optional[str] = None,
        players_count: int = 0,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        **kwargs
    ):
        self._id = None
        self.server_id = server_id
        self.guild_id = guild_id
        self.name = name
        self.description = description
        self.status = status
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.sftp_directory = sftp_directory
        self.log_directory = log_directory
        self.last_checked = last_checked
        self.last_error = last_error
        self.players_count = players_count
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        
        # Add any additional server attributes
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    async def get_by_server_id(cls, db, server_id: str) -> Optional['Server']:
        """Get a server by server_id
        
        Args:
            db: Database connection
            server_id: Server ID
            
        Returns:
            Server object or None if not found
        """
        document = await db.game_servers.find_one({"server_id": server_id})
        return cls.from_document(document) if document else None
    
    @classmethod
    async def get_by_name(cls, db, name: str, guild_id: str) -> Optional['Server']:
        """Get a server by name and guild_id
        
        Args:
            db: Database connection
            name: Server name
            guild_id: Guild ID
            
        Returns:
            Server object or None if not found
        """
        document = await db.game_servers.find_one({"name": name, "guild_id": guild_id})
        return cls.from_document(document) if document else None
    
    @classmethod
    async def get_servers_for_guild(cls, db, guild_id: str) -> List['Server']:
        """Get all servers for a guild
        
        Args:
            db: Database connection
            guild_id: Guild ID
            
        Returns:
            List of Server objects
        """
        cursor = db.game_servers.find({"guild_id": guild_id})
        
        servers = []
        async for document in cursor:
            servers.append(cls.from_document(document))
            
        return servers
    
    async def update_status(self, db, status: str, error_message: Optional[str] = None) -> bool:
        """Update server status
        
        Args:
            db: Database connection
            status: New status
            error_message: Optional error message
            
        Returns:
            True if updated successfully, False otherwise
        """
        if status not in [self.STATUS_ACTIVE, self.STATUS_INACTIVE, self.STATUS_ERROR, self.STATUS_MAINTENANCE]:
            return False
            
        self.status = status
        self.last_checked = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        if error_message is not None and status == self.STATUS_ERROR:
            self.last_error = error_message
            
        # Update in database
        update_dict = {
            "status": self.status,
            "last_checked": self.last_checked,
            "updated_at": self.updated_at
        }
        
        if error_message is not None and status == self.STATUS_ERROR:
            update_dict["last_error"] = self.last_error
        
        result = await db.game_servers.update_one(
            {"server_id": self.server_id},
            {"$set": update_dict}
        )
        
        return result.modified_count > 0
    
    async def update_sftp_credentials(self, db, hostname: str, port: int, username: str, password: str, sftp_directory: str) -> bool:
        """Update SFTP credentials
        
        Args:
            db: Database connection
            hostname: SFTP hostname
            port: SFTP port
            username: SFTP username
            password: SFTP password
            sftp_directory: SFTP directory
            
        Returns:
            True if updated successfully, False otherwise
        """
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.sftp_directory = sftp_directory
        self.updated_at = datetime.utcnow()
        
        # Update in database
        result = await db.game_servers.update_one(
            {"server_id": self.server_id},
            {"$set": {
                "hostname": self.hostname,
                "port": self.port,
                "username": self.username,
                "password": self.password,
                "sftp_directory": self.sftp_directory,
                "updated_at": self.updated_at
            }}
        )
        
        return result.modified_count > 0
    
    async def update_log_directory(self, db, log_directory: str) -> bool:
        """Update log directory
        
        Args:
            db: Database connection
            log_directory: Log directory
            
        Returns:
            True if updated successfully, False otherwise
        """
        self.log_directory = log_directory
        self.updated_at = datetime.utcnow()
        
        # Update in database
        result = await db.game_servers.update_one(
            {"server_id": self.server_id},
            {"$set": {
                "log_directory": self.log_directory,
                "updated_at": self.updated_at
            }}
        )
        
        return result.modified_count > 0
    
    @classmethod
    async def create_server(
        cls, 
        db, 
        guild_id: str,
        name: str,
        description: Optional[str] = None,
        hostname: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        sftp_directory: Optional[str] = None,
        log_directory: Optional[str] = None
    ) -> Optional['Server']:
        """Create a new server
        
        Args:
            db: Database connection
            guild_id: Guild ID
            name: Server name
            description: Server description
            hostname: SFTP hostname
            port: SFTP port
            username: SFTP username
            password: SFTP password
            sftp_directory: SFTP directory
            log_directory: Log directory
            
        Returns:
            Server object or None if creation failed
        """
        import uuid
        
        # Create server ID
        server_id = str(uuid.uuid4())
        
        # Check if server with this name already exists for this guild
        existing_server = await cls.get_by_name(db, name, guild_id)
        if existing_server:
            logger.error(f"Server with name {name} already exists for guild {guild_id}")
            return None
            
        # Create server object
        now = datetime.utcnow()
        server = cls(
            server_id=server_id,
            guild_id=guild_id,
            name=name,
            description=description,
            status=cls.STATUS_INACTIVE,  # Start as inactive until verified
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            sftp_directory=sftp_directory,
            log_directory=log_directory,
            last_checked=now,
            players_count=0,
            created_at=now,
            updated_at=now
        )
        
        # Insert into database
        try:
            await db.game_servers.insert_one(server.to_document())
            return server
        except Exception as e:
            logger.error(f"Error creating server: {e}")
            return None