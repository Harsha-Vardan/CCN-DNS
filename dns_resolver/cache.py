import time
from collections import OrderedDict
from .config import *
from .utils import get_logger

logger = get_logger(__name__)

class DNSCache:
    def __init__(self, capacity=CACHE_SIZE):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        """
        Retrieves a record from the cache.
        Key should be (domain, record_type).
        """
        if key in self.cache:
            record, timestamp = self.cache[key]
            
            # Check TTL
            ttl = record.get('ttl', DEFAULT_TTL)
            if time.time() - timestamp < ttl:
                self.cache.move_to_end(key)
                self.hits += 1
                logger.info(f"Cache HIT for {key}")
                return record
            else:
                # Expired
                del self.cache[key]
                self.misses += 1
                logger.info(f"Cache EXPIRED for {key}")
                return None
        
        self.misses += 1
        logger.info(f"Cache MISS for {key}")
        return None

    def put(self, key, record):
        """
        Adds a record to the cache.
        """
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (record, time.time())
        
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
            
    def get_stats(self):
        return {
            'hits': self.hits,
            'misses': self.misses,
            'size': len(self.cache),
            'capacity': self.capacity
        }
