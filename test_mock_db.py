"""
MongoDB mock for testing the bounty system

This module provides a mock implementation of the MongoDB database
to allow testing of the bounty system without requiring a live
MongoDB connection.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockInsertOneResult:
    """Mock insert one result"""
    
    def __init__(self, inserted_id):
        """Initialize result
        
        Args:
            inserted_id: ID of inserted document
        """
        self.inserted_id = inserted_id


class MockInsertManyResult:
    """Mock insert many result"""
    
    def __init__(self, inserted_ids):
        """Initialize result
        
        Args:
            inserted_ids: IDs of inserted documents
        """
        self.inserted_ids = inserted_ids


class MockUpdateResult:
    """Mock update result"""
    
    def __init__(self, modified_count, upserted_id):
        """Initialize result
        
        Args:
            modified_count: Number of documents modified
            upserted_id: ID of upserted document
        """
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class MockDeleteResult:
    """Mock delete result"""
    
    def __init__(self, deleted_count):
        """Initialize result
        
        Args:
            deleted_count: Number of documents deleted
        """
        self.deleted_count = deleted_count


class MockCursor:
    """Mock MongoDB cursor"""
    
    def __init__(self, documents: List[Dict[str, Any]]):
        """Initialize cursor
        
        Args:
            documents: Documents to iterate
        """
        self.documents = documents
        self.current_position = 0
        
    def sort(self, key_or_list, direction=None):
        """Sort documents
        
        Args:
            key_or_list: Sort key or list of (key, direction) pairs
            direction: Sort direction (only used if key_or_list is a string)
            
        Returns:
            Self for chaining
        """
        # Not implemented yet
        logger.warning("Mock sort not implemented")
        return self
        
    def skip(self, count: int):
        """Skip documents
        
        Args:
            count: Number of documents to skip
            
        Returns:
            Self for chaining
        """
        if count > 0:
            self.current_position = min(len(self.documents), count)
        return self
        
    def limit(self, count: int):
        """Limit documents
        
        Args:
            count: Maximum number of documents to return
            
        Returns:
            Self for chaining
        """
        if count > 0:
            self.documents = self.documents[:min(len(self.documents), self.current_position + count)]
        return self
        
    async def to_list(self, length=None):
        """Convert cursor to list
        
        Args:
            length: Maximum number of documents to return
            
        Returns:
            List of documents
        """
        if length is None:
            return self.documents[self.current_position:]
        return self.documents[self.current_position:self.current_position + length]
        
    def __aiter__(self):
        """Initialize async iterator"""
        self.current_position = 0
        return self
        
    async def __anext__(self):
        """Get next document"""
        if self.current_position >= len(self.documents):
            raise StopAsyncIteration
            
        doc = self.documents[self.current_position]
        self.current_position += 1
        return doc


class MockCollection:
    """Mock MongoDB collection"""
    
    def __init__(self, name: str):
        """Initialize collection
        
        Args:
            name: Collection name
        """
        self.name = name
        self.documents = []
        self.indexes = []
        
    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find one document
        
        Args:
            query: Query to match documents
            
        Returns:
            Document or None
        """
        for doc in self.documents:
            if self._matches_query(doc, query):
                return doc
        return None
        
    async def find(self, query: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Find documents
        
        Args:
            query: Query to match documents
            
        Returns:
            List of matching documents
        """
        if query is None:
            query = {}
            
        results = [doc for doc in self.documents if self._matches_query(doc, query)]
        return MockCursor(results)
        
    async def count_documents(self, query: Dict[str, Any]) -> int:
        """Count documents
        
        Args:
            query: Query to match documents
            
        Returns:
            Number of matching documents
        """
        return len([doc for doc in self.documents if self._matches_query(doc, query)])
        
    async def insert_one(self, document: Dict[str, Any]) -> MockInsertOneResult:
        """Insert one document
        
        Args:
            document: Document to insert
            
        Returns:
            Insert result
        """
        # Generate ID if not provided
        if '_id' not in document:
            document['_id'] = str(uuid.uuid4())
            
        self.documents.append(document)
        return MockInsertOneResult(document['_id'])
        
    async def insert_many(self, documents: List[Dict[str, Any]]) -> MockInsertManyResult:
        """Insert many documents
        
        Args:
            documents: Documents to insert
            
        Returns:
            Insert result
        """
        ids = []
        for doc in documents:
            # Generate ID if not provided
            if '_id' not in doc:
                doc['_id'] = str(uuid.uuid4())
                
            self.documents.append(doc)
            ids.append(doc['_id'])
            
        return MockInsertManyResult(ids)
        
    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> MockUpdateResult:
        """Update one document
        
        Args:
            query: Query to match document
            update: Update operations
            upsert: Whether to insert if not exists
            
        Returns:
            Update result
        """
        for i, doc in enumerate(self.documents):
            if self._matches_query(doc, query):
                self._apply_update(self.documents[i], update)
                return MockUpdateResult(1, None)
                
        # If no document matched and upsert is True, insert new document
        if upsert:
            new_doc = {}
            for key, value in query.items():
                new_doc[key] = value
                
            self._apply_update(new_doc, update)
            self.documents.append(new_doc)
            return MockUpdateResult(0, new_doc['_id'])
            
        return MockUpdateResult(0, None)
        
    async def update_many(self, query: Dict[str, Any], update: Dict[str, Any]) -> MockUpdateResult:
        """Update many documents
        
        Args:
            query: Query to match documents
            update: Update operations
            
        Returns:
            Update result
        """
        count = 0
        for i, doc in enumerate(self.documents):
            if self._matches_query(doc, query):
                self._apply_update(self.documents[i], update)
                count += 1
                
        return MockUpdateResult(count, None)
        
    async def delete_one(self, query: Dict[str, Any]) -> MockDeleteResult:
        """Delete one document
        
        Args:
            query: Query to match document
            
        Returns:
            Delete result
        """
        for i, doc in enumerate(self.documents):
            if self._matches_query(doc, query):
                del self.documents[i]
                return MockDeleteResult(1)
                
        return MockDeleteResult(0)
        
    async def delete_many(self, query: Dict[str, Any]) -> MockDeleteResult:
        """Delete many documents
        
        Args:
            query: Query to match documents
            
        Returns:
            Delete result
        """
        initial_count = len(self.documents)
        self.documents = [doc for doc in self.documents if not self._matches_query(doc, query)]
        deleted_count = initial_count - len(self.documents)
        return MockDeleteResult(deleted_count)
        
    async def create_index(self, keys: List[Tuple[str, int]], **kwargs) -> str:
        """Create index
        
        Args:
            keys: Index keys
            **kwargs: Index options
            
        Returns:
            Index name
        """
        name = kwargs.get('name', f"index_{len(self.indexes)}")
        self.indexes.append({
            'name': name,
            'keys': keys,
            'options': kwargs
        })
        return name
        
    async def create_indexes(self, indexes: List[Any]) -> List[str]:
        """Create multiple indexes
        
        Args:
            indexes: List of index models
            
        Returns:
            List of index names
        """
        names = []
        for index in indexes:
            name = await self.create_index(index.document['key'], **index.document.get('options', {}))
            names.append(name)
        return names
        
    async def drop_index(self, name: str) -> None:
        """Drop index
        
        Args:
            name: Index name
        """
        self.indexes = [idx for idx in self.indexes if idx['name'] != name]
        
    async def drop_indexes(self) -> None:
        """Drop all indexes"""
        self.indexes = []
        
    async def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aggregate documents
        
        Args:
            pipeline: Aggregation pipeline
            
        Returns:
            List of results
        """
        # Simple implementation for basic aggregation stages
        results = self.documents.copy()
        
        for stage in pipeline:
            if '$match' in stage:
                results = [doc for doc in results if self._matches_query(doc, stage['$match'])]
            elif '$group' in stage:
                # Basic grouping - not fully implemented
                logger.warning("Mock aggregation $group stage not fully implemented")
            elif '$sort' in stage:
                # Basic sorting - not fully implemented
                logger.warning("Mock aggregation $sort stage not fully implemented")
                
        return MockCursor(results)
        
    def _matches_query(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        """Check if document matches query
        
        Args:
            doc: Document to check
            query: Query to match
            
        Returns:
            True if document matches query
        """
        for key, value in query.items():
            if key == '$and':
                # $and operator
                for sub_query in value:
                    if not self._matches_query(doc, sub_query):
                        return False
                continue
                
            if key == '$or':
                # $or operator
                if not any(self._matches_query(doc, sub_query) for sub_query in value):
                    return False
                continue
                
            if key not in doc:
                return False
                
            if isinstance(value, dict):
                # Operators
                for op, op_value in value.items():
                    if op == '$gt':
                        if not doc[key] > op_value:
                            return False
                    elif op == '$gte':
                        if not doc[key] >= op_value:
                            return False
                    elif op == '$lt':
                        if not doc[key] < op_value:
                            return False
                    elif op == '$lte':
                        if not doc[key] <= op_value:
                            return False
                    elif op == '$ne':
                        if not doc[key] != op_value:
                            return False
                    elif op == '$in':
                        if not doc[key] in op_value:
                            return False
                    elif op == '$nin':
                        if doc[key] in op_value:
                            return False
                    elif op == '$exists':
                        if op_value and key not in doc:
                            return False
                        if not op_value and key in doc:
                            return False
            else:
                # Direct comparison
                if doc[key] != value:
                    return False
                    
        return True
        
    def _apply_update(self, doc: Dict[str, Any], update: Dict[str, Any]) -> None:
        """Apply update operations to document
        
        Args:
            doc: Document to update
            update: Update operations
        """
        for op, fields in update.items():
            if op == '$set':
                # Set fields
                for field, value in fields.items():
                    doc[field] = value
            elif op == '$unset':
                # Unset fields
                for field in fields:
                    if field in doc:
                        del doc[field]
            elif op == '$inc':
                # Increment fields
                for field, value in fields.items():
                    if field in doc:
                        doc[field] += value
                    else:
                        doc[field] = value
            elif op == '$push':
                # Push to arrays
                for field, value in fields.items():
                    if field not in doc:
                        doc[field] = []
                    doc[field].append(value)
            elif op == '$pull':
                # Pull from arrays
                for field, value in fields.items():
                    if field in doc and isinstance(doc[field], list):
                        doc[field] = [item for item in doc[field] if item != value]


class MockCursor:
    """Mock MongoDB cursor"""
    
    def __init__(self, documents: List[Dict[str, Any]]):
        """Initialize cursor
        
        Args:
            documents: Documents to iterate
        """
        self.documents = documents
        self.current_position = 0
        
    def sort(self, key_or_list, direction=None):
        """Sort documents
        
        Args:
            key_or_list: Sort key or list of (key, direction) pairs
            direction: Sort direction (only used if key_or_list is a string)
            
        Returns:
            Self for chaining
        """
        # Not implemented yet
        logger.warning("Mock sort not implemented")
        return self
        
    def skip(self, count: int):
        """Skip documents
        
        Args:
            count: Number of documents to skip
            
        Returns:
            Self for chaining
        """
        if count > 0:
            self.current_position = min(len(self.documents), count)
        return self
        
    def limit(self, count: int):
        """Limit documents
        
        Args:
            count: Maximum number of documents to return
            
        Returns:
            Self for chaining
        """
        if count > 0:
            self.documents = self.documents[:min(len(self.documents), self.current_position + count)]
        return self
        
    async def to_list(self, length=None):
        """Convert cursor to list
        
        Args:
            length: Maximum number of documents to return
            
        Returns:
            List of documents
        """
        if length is None:
            return self.documents[self.current_position:]
        return self.documents[self.current_position:self.current_position + length]
        
    def __aiter__(self):
        """Initialize async iterator"""
        self.current_position = 0
        return self
        
    async def __anext__(self):
        """Get next document"""
        if self.current_position >= len(self.documents):
            raise StopAsyncIteration
            
        doc = self.documents[self.current_position]
        self.current_position += 1
        return doc


class MockInsertOneResult:
    """Mock insert one result"""
    
    def __init__(self, inserted_id):
        """Initialize result
        
        Args:
            inserted_id: ID of inserted document
        """
        self.inserted_id = inserted_id


class MockInsertManyResult:
    """Mock insert many result"""
    
    def __init__(self, inserted_ids):
        """Initialize result
        
        Args:
            inserted_ids: IDs of inserted documents
        """
        self.inserted_ids = inserted_ids


class MockUpdateResult:
    """Mock update result"""
    
    def __init__(self, modified_count, upserted_id):
        """Initialize result
        
        Args:
            modified_count: Number of documents modified
            upserted_id: ID of upserted document
        """
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class MockDeleteResult:
    """Mock delete result"""
    
    def __init__(self, deleted_count):
        """Initialize result
        
        Args:
            deleted_count: Number of documents deleted
        """
        self.deleted_count = deleted_count


class MockDatabase:
    """Mock MongoDB database"""
    
    def __init__(self, name: str):
        """Initialize database
        
        Args:
            name: Database name
        """
        self.name = name
        self.collections = {}
        
    def __getitem__(self, name: str) -> MockCollection:
        """Get collection
        
        Args:
            name: Collection name
            
        Returns:
            Collection
        """
        if name not in self.collections:
            self.collections[name] = MockCollection(name)
        return self.collections[name]
        
    def get_collection(self, name: str) -> MockCollection:
        """Get collection
        
        Args:
            name: Collection name
            
        Returns:
            Collection
        """
        return self[name]
        
    async def list_collection_names(self) -> List[str]:
        """List collection names
        
        Returns:
            List of collection names
        """
        return list(self.collections.keys())
        
    async def create_collection(self, name: str) -> MockCollection:
        """Create collection
        
        Args:
            name: Collection name
            
        Returns:
            Collection
        """
        if name not in self.collections:
            self.collections[name] = MockCollection(name)
        return self.collections[name]


class MockClient:
    """Mock MongoDB client"""
    
    def __init__(self):
        """Initialize client"""
        self.dbs = {}
        self.io_loop = MockIOLoop()
        self.server_info = {"version": "mock"}
        
    def __getitem__(self, name: str) -> MockDatabase:
        """Get database
        
        Args:
            name: Database name
            
        Returns:
            Database
        """
        if name not in self.dbs:
            self.dbs[name] = MockDatabase(name)
        return self.dbs[name]
        
    def get_database(self, name: str) -> MockDatabase:
        """Get database
        
        Args:
            name: Database name
            
        Returns:
            Database
        """
        return self[name]
        
    def close(self) -> None:
        """Close client connection"""
        pass
        
    async def server_info(self) -> Dict[str, Any]:
        """Get server info
        
        Returns:
            Server info
        """
        return {"version": "mock"}
        
    @property
    def admin(self):
        """Get admin database"""
        return MockAdmin()


class MockAdmin:
    """Mock MongoDB admin database"""
    
    async def command(self, command: str, *args, **kwargs) -> Dict[str, Any]:
        """Run command
        
        Args:
            command: Command to run
            *args: Command arguments
            **kwargs: Command options
            
        Returns:
            Command result
        """
        if command == "ping":
            return {"ok": 1}
            
        return {"ok": 0, "errmsg": f"Unknown command: {command}"}


class MockIOLoop:
    """Mock IO loop"""
    
    def is_closed(self) -> bool:
        """Check if loop is closed
        
        Returns:
            False (mock is never closed)
        """
        return False


class MockDatabaseManager:
    """Mock MongoDB database manager"""
    
    def __init__(self, db_name: str = "test"):
        """Initialize database manager
        
        Args:
            db_name: Database name
        """
        self.db_name = db_name
        self.client = MockClient()
        self.db = self.client[db_name]
        self._connected = True
        self.players = self.db["players"]
        self.guilds = self.db["guilds"]
        self.collections = {}
        
    async def connect(self) -> bool:
        """Connect to database
        
        Returns:
            True (mock is always connected)
        """
        return True
        
    async def disconnect(self) -> None:
        """Disconnect from database"""
        pass
        
    def __getattr__(self, name: str) -> Any:
        """Get attribute
        
        Args:
            name: Attribute name
            
        Returns:
            Attribute value
        """
        # Allow access to collections as attributes
        if name in self.db.collections:
            return self.db[name]
            
        # For testing bounties collection
        if name == "collections":
            # Initialize collections dict if needed
            if not hasattr(self, "_collections"):
                self._collections = {}
                
            # Create proxy to access collections
            class CollectionsProxy:
                def __getitem__(proxy_self, collection_name: str) -> MockCollection:
                    if collection_name not in self._collections:
                        self._collections[collection_name] = self.db[collection_name]
                    return self._collections[collection_name]
                    
            return CollectionsProxy()
            
        raise AttributeError(f"'MockDatabaseManager' has no attribute '{name}'")


# Mock get_db function for testing
_mock_db = None

async def get_mock_db() -> MockDatabaseManager:
    """Get mock database manager
    
    Returns:
        Mock database manager
    """
    global _mock_db
    
    if not _mock_db:
        _mock_db = MockDatabaseManager("test")
        
    return _mock_db


class IndexModel:
    """Mock index model for creating indexes"""
    
    def __init__(self, keys, **kwargs):
        """Initialize index model
        
        Args:
            keys: Index keys
            **kwargs: Index options
        """
        if isinstance(keys, list):
            self.document = {"key": keys, "options": kwargs}
        else:
            self.document = {"key": [(keys, 1)], "options": kwargs}


# For testing
if __name__ == "__main__":
    async def test_mock_db():
        """Test mock database"""
        db = await get_mock_db()
        
        # Test collections
        players = db.players
        assert players is not None
        
        # Test insert
        player_data = {
            "player_id": "123",
            "player_name": "TestPlayer",
            "server_id": "test_server",
            "currency": 1000
        }
        result = await players.insert_one(player_data)
        assert result.inserted_id is not None
        
        # Test find
        player = await players.find_one({"player_id": "123"})
        assert player is not None
        assert player["player_name"] == "TestPlayer"
        
        # Test update
        update_result = await players.update_one(
            {"player_id": "123"},
            {"$set": {"currency": 1500}}
        )
        assert update_result.modified_count == 1
        
        player = await players.find_one({"player_id": "123"})
        assert player["currency"] == 1500
        
        # Test collections proxy
        bounties = db.collections["bounties"]
        assert bounties is not None
        
        bounty_data = {
            "guild_id": "456",
            "server_id": "test_server",
            "target_id": "123",
            "target_name": "TestPlayer",
            "placed_by": "789",
            "placed_by_name": "PosterPlayer",
            "placed_at": datetime.utcnow(),
            "reason": "Test bounty",
            "reward": 500,
            "status": "active"
        }
        result = await bounties.insert_one(bounty_data)
        assert result.inserted_id is not None
        
        bounty = await bounties.find_one({"target_id": "123"})
        assert bounty is not None
        assert bounty["reward"] == 500
        
        # Test delete
        delete_result = await bounties.delete_one({"target_id": "123"})
        assert delete_result.deleted_count == 1
        
        bounty = await bounties.find_one({"target_id": "123"})
        assert bounty is None
        
        print("All tests passed!")
    
    # Run tests
    asyncio.run(test_mock_db())