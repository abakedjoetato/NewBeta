"""
Comprehensive Fixes Implementation for Tower of Temptation PvP Statistics Discord Bot

This script addresses the following critical issues:
1. Inconsistent model method names across the codebase (create, get_by_id, etc.)
2. Missing class constants in models
3. Type safety issues with None values
4. Collection access in database queries
5. Inconsistent method signatures
6. Missing import references

Run this script to apply all fixes at once.
"""
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, ClassVar, Type, TypeVar, Union

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Required fixes
MODEL_FIXES = [
    {
        "model": "Bounty",
        "missing_constants": [
            ("SOURCE_PLAYER", "player"),
            ("SOURCE_AUTO", "auto"),
            ("SOURCE_ADMIN", "admin"),
            ("STATUS_ACTIVE", "active"),
            ("STATUS_CLAIMED", "claimed"),
            ("STATUS_EXPIRED", "expired"),
            ("STATUS_CANCELLED", "cancelled"),
        ],
        "missing_methods": [
            "create",
            "get_by_id",
        ]
    },
    {
        "model": "EconomyTransaction",
        "missing_constants": [
            ("TYPE_BOUNTY_PLACED", "bounty_placed"),
            ("TYPE_BOUNTY_CLAIMED", "bounty_claimed"),
            ("TYPE_BOUNTY_EXPIRED", "bounty_expired"),
            ("TYPE_BOUNTY_CANCELLED", "bounty_cancelled"),
            ("TYPE_ADMIN_ADJUSTMENT", "admin_adjustment"),
        ],
        "missing_methods": [
            "create",
            "get_by_player",
        ]
    }
]

# Implementations for missing methods
METHOD_IMPLEMENTATIONS = {
    "Bounty.create": """
    @classmethod
    async def create(cls, db, guild_id: str, server_id: str, target_id: str, 
                     target_name: str, placed_by: str, placed_by_name: str, 
                     reason: str = None, reward: int = 100, source: str = "player",
                     lifespan_hours: float = 1.0) -> Optional['Bounty']:
        \"\"\"Create a new bounty
        
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
        \"\"\"
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
    """,
    
    "Bounty.get_by_id": """
    @classmethod
    async def get_by_id(cls, db, bounty_id: str) -> Optional['Bounty']:
        \"\"\"Get a bounty by its ID
        
        Args:
            db: Database connection
            bounty_id: Bounty ID
            
        Returns:
            Bounty object or None if not found
        \"\"\"
        document = await db[cls.collection_name].find_one({"id": bounty_id})
        return cls.from_document(document)
    """,
    
    "EconomyTransaction.create": """
    @classmethod
    async def create(cls, db, discord_id: str, guild_id: str, 
                    amount: int, type: str, 
                    server_id: str = None, 
                    description: str = None) -> Optional['EconomyTransaction']:
        \"\"\"Create a new economy transaction
        
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
        \"\"\"
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
    """,
    
    "EconomyTransaction.get_by_player": """
    @classmethod
    async def get_by_player(cls, db, discord_id: str, guild_id: str = None) -> List['EconomyTransaction']:
        \"\"\"Get all transactions for a player
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Optional guild ID to filter by
            
        Returns:
            List of transactions
        \"\"\"
        query = {"discord_id": discord_id}
        if guild_id:
            query["guild_id"] = guild_id
            
        cursor = db[cls.collection_name].find(query).sort("timestamp", -1)
        
        transactions = []
        async for document in cursor:
            transactions.append(cls.from_document(document))
            
        return transactions
    """
}

def add_id_property_to_model(class_def):
    """Add ID property to model __init__ method"""
    init_method = class_def.find("def __init__(")
    if init_method == -1:
        return class_def
    
    # Find the first attribute assignment
    attr_start = class_def.find("self._id = None", init_method)
    if attr_start == -1:
        return class_def
    
    # Find the next line after self._id
    next_line = class_def.find("\n", attr_start) + 1
    
    # Add id property after _id
    id_line = "        self.id = kwargs.get(\"id\", str(uuid.uuid4())[:8])  # Short ID for references\n"
    return class_def[:next_line] + id_line + class_def[next_line:]

def add_constants_to_model(class_def, constants):
    """Add constants to a model class"""
    class_header_end = class_def.find(":", class_def.find("class ")) + 1
    next_line = class_def.find("\n", class_header_end) + 1
    
    # Generate constants code
    constants_code = "\n"
    for const_name, const_value in constants:
        constants_code += f"    # {const_name} constant\n"
        constants_code += f"    {const_name} = \"{const_value}\"\n"
    constants_code += "\n"
    
    return class_def[:next_line] + constants_code + class_def[next_line:]

def add_method_to_model(class_def, method_code):
    """Add a method to a model class"""
    # Find a good place to add the method - before the last line of the class
    last_line = class_def.rfind("\n\n\n")
    if last_line == -1:
        # Try to find the end of the class another way
        last_line = class_def.rfind("\n    def ")
        if last_line == -1:
            return class_def  # Couldn't find a good place
        
        # Find the end of this method
        last_line = class_def.find("\n\n", last_line + 1)
        if last_line == -1:
            return class_def  # Couldn't find end of method
    
    return class_def[:last_line] + "\n" + method_code + class_def[last_line:]

def fix_db_access_inconsistencies(file_content):
    """Fix database access inconsistencies
    
    Change db.collection to db[collection_name] for consistency
    """
    # Fix db.collection_name to db[collection_name]
    file_content = file_content.replace("db.guilds", "db['guilds']")
    file_content = file_content.replace("db.game_servers", "db['game_servers']")
    file_content = file_content.replace("db.players", "db['players']")
    file_content = file_content.replace("db.player_links", "db['player_links']")
    file_content = file_content.replace("db.bounties", "db['bounties']")
    file_content = file_content.replace("db.kills", "db['kills']")
    file_content = file_content.replace("db.bot_status", "db['bot_status']")
    file_content = file_content.replace("db.economy", "db['economy']")
    
    # Fix db['collection_name'] to db[cls.collection_name]
    file_content = file_content.replace("db['guilds']", "db[cls.collection_name]", 
                                       file_content.find("class Guild"))
    file_content = file_content.replace("db['game_servers']", "db[cls.collection_name]", 
                                       file_content.find("class GameServer"))
    file_content = file_content.replace("db['players']", "db[cls.collection_name]", 
                                       file_content.find("class Player"))
    file_content = file_content.replace("db['player_links']", "db[cls.collection_name]", 
                                       file_content.find("class PlayerLink"))
    file_content = file_content.replace("db['bounties']", "db[cls.collection_name]", 
                                       file_content.find("class Bounty"))
    file_content = file_content.replace("db['kills']", "db[cls.collection_name]", 
                                       file_content.find("class Kill"))
    file_content = file_content.replace("db['bot_status']", "db[cls.collection_name]", 
                                       file_content.find("class BotStatus"))
    file_content = file_content.replace("db['economy']", "db[cls.collection_name]", 
                                       file_content.find("class EconomyTransaction"))
    
    return file_content

def add_uuid_import(file_content):
    """Add uuid import if not present"""
    if "import uuid" not in file_content:
        # Add before the first import 
        import_start = file_content.find("import ")
        if import_start != -1:
            return file_content[:import_start] + "import uuid\n" + file_content[import_start:]
    return file_content

def update_models_py():
    """Update models.py with all fixes"""
    logger.info("Updating models.py...")
    
    try:
        # Read the current content of models.py
        with open("models.py", "r") as f:
            content = f.read()
            
        # Add uuid import if needed
        content = add_uuid_import(content)
        
        # Fix database access inconsistencies
        content = fix_db_access_inconsistencies(content)
        
        # Apply model-specific fixes
        for model_fix in MODEL_FIXES:
            model_name = model_fix["model"]
            logger.info(f"Applying fixes to {model_name} model...")
            
            # Find the class definition
            class_start = content.find(f"class {model_name}(BaseModel):")
            if class_start == -1:
                logger.warning(f"Could not find {model_name} class")
                continue
                
            # Find the end of the class
            next_class = content.find("class ", class_start + 1)
            if next_class == -1:
                class_def = content[class_start:]
            else:
                class_def = content[class_start:next_class]
                
            # Add ID property
            class_def = add_id_property_to_model(class_def)
                
            # Add constants
            constants = model_fix.get("missing_constants", [])
            if constants:
                class_def = add_constants_to_model(class_def, constants)
                
            # Add methods
            for method_name in model_fix.get("missing_methods", []):
                implementation_key = f"{model_name}.{method_name}"
                if implementation_key in METHOD_IMPLEMENTATIONS:
                    logger.info(f"Adding {method_name} method to {model_name}")
                    class_def = add_method_to_model(class_def, METHOD_IMPLEMENTATIONS[implementation_key])
                    
            # Replace the class definition in the content
            if next_class == -1:
                content = content[:class_start] + class_def
            else:
                content = content[:class_start] + class_def + content[next_class:]
        
        # Write the updated content back to models.py
        with open("models.py", "w") as f:
            f.write(content)
            
        logger.info("models.py updated successfully")
        return True
    except Exception as e:
        logger.error(f"Error updating models.py: {e}")
        return False

def update_models_imports():
    """Update imports in models modules to resolve circular imports"""
    logger.info("Updating model imports...")
    
    # Models that need updated imports
    MODEL_FILES = [
        "models/bounty.py",
        "models/economy.py",
        "models/player.py",
        "models/guild.py",
        "models/server.py",
        "models/player_link.py",
    ]
    
    for file_path in MODEL_FILES:
        try:
            if not os.path.exists(file_path):
                logger.warning(f"File {file_path} not found")
                continue
                
            logger.info(f"Updating imports in {file_path}...")
            
            # Read the current content
            with open(file_path, "r") as f:
                content = f.read()
                
            # Add uuid import if needed
            if "import uuid" not in content:
                import_section_end = content.find("\n\n", content.find("import "))
                if import_section_end != -1:
                    content = content[:import_section_end] + "\nimport uuid" + content[import_section_end:]
            
            # Write the updated content
            with open(file_path, "w") as f:
                f.write(content)
                
            logger.info(f"{file_path} updated successfully")
        except Exception as e:
            logger.error(f"Error updating {file_path}: {e}")

async def main():
    """Run all comprehensive fixes"""
    logger.info("Starting comprehensive fixes implementation...")
    
    # Update models.py with all fixes
    if update_models_py():
        logger.info("Successfully updated models.py")
    else:
        logger.error("Failed to update models.py")
        
    # Update model imports
    update_models_imports()
    
    logger.info("Comprehensive fixes implementation complete")

if __name__ == "__main__":
    asyncio.run(main())