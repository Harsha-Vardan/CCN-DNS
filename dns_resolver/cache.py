from .config import *
from .utils import get_logger
from .storage import MemoryStorage, MongoStorage, PostgresStorage

logger = get_logger(__name__)

class DNSCache:
    def __init__(self, capacity=CACHE_SIZE):
        self.capacity = capacity
        self.backend_type = CACHE_BACKEND
        self.storage = self._initialize_storage()

    def _initialize_storage(self):
        if self.backend_type == 'mongodb':
            try:
                return MongoStorage()
            except Exception as e:
                logger.error(f"Failed to initialize MongoDB backend, falling back to memory: {e}")
                return MemoryStorage(self.capacity)
        elif self.backend_type == 'postgresql':
            try:
                return PostgresStorage()
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL backend, falling back to memory: {e}")
                return MemoryStorage(self.capacity)
        else:
            return MemoryStorage(self.capacity)

    def get(self, key):
        """
        Retrieves a record from the cache.
        Key should be (domain, record_type).
        """
        result = self.storage.get(key)
        if result:
            record, timestamp = result
            logger.info(f"Cache HIT for {key}")
            return record
        
        logger.info(f"Cache MISS for {key}")
        return None

    def put(self, key, record):
        """
        Adds a record to the cache.
        """
        self.storage.put(key, record)
            
    def get_stats(self):
        return self.storage.get_stats()

    def get_all(self):
        """
        Returns all cache entries.
        """
        return self.storage.get_all()

    def clear(self):
        """
        Clears the cache.
        """
        self.storage.clear()
