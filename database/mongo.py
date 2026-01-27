from pymongo import MongoClient
from django.conf import settings

class MongoDB:
    """Singleton MongoDB connection manager"""
    _instance = None
    _client = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDB, cls).__new__(cls)
            cls._client = MongoClient(settings.MONGODB_URI)
            cls._db = cls._client[settings.MONGODB_DB_NAME]
            
            # Create indexes
            cls._create_indexes()
        return cls._instance
    
    @classmethod
    def _create_indexes(cls):
        """Create unique indexes for collections"""
        users = cls._db.users
        
        # Create unique index on uid (primary identifier for all users)
        try:
            users.create_index('uid', unique=True)
        except:
            pass  # Index might already exist
        
        # Create unique index on phone for fast lookups
        try:
            users.create_index('phone', unique=True)
        except:
            pass  # Index might already exist
        
        # firebase_uid NO LONGER has unique constraint
        # It's optional for backend OTP users
    
    @classmethod
    def get_db(cls):
        """Get the database instance"""
        if cls._db is None:
            cls()
        return cls._db
    
    @classmethod
    def get_collection(cls, collection_name):
        """Get a specific collection"""
        db = cls.get_db()
        return db[collection_name]


# Convenience functions
def get_users_collection():
    return MongoDB.get_collection('users')
