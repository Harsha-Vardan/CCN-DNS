import time
import pickle
from abc import ABC, abstractmethod
from collections import OrderedDict
from .config import *
from .utils import get_logger

logger = get_logger(__name__)

class CacheStorage(ABC):
    @abstractmethod
    def get(self, key):
        """
        Retrieve a record from storage.
        Key is (domain, record_type).
        Returns (record, timestamp) or None.
        """
        pass

    @abstractmethod
    def put(self, key, record):
        """
        Save a record to storage.
        """
        pass

    @abstractmethod
    def get_stats(self):
        """
        Return storage statistics.
        """
        pass

    @abstractmethod
    def get_all(self):
        """
        Return all records in cache as a list of (key, value) tuples.
        Value is (record, timestamp).
        """
        pass

    @abstractmethod
    def clear(self):
        """
        Clear all records from storage.
        """
        pass

class MemoryStorage(CacheStorage):
    def __init__(self, capacity=CACHE_SIZE):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        if key in self.cache:
            record, timestamp = self.cache[key]
            # Check TTL
            ttl = record.get('ttl', DEFAULT_TTL)
            if time.time() - timestamp < ttl:
                self.cache.move_to_end(key)
                self.hits += 1
                return record, timestamp
            else:
                del self.cache[key]
                self.misses += 1
                return None
        self.misses += 1
        return None

    def put(self, key, record):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (record, time.time())
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def get_stats(self):
        return {
            'type': 'memory',
            'hits': self.hits,
            'misses': self.misses,
            'size': len(self.cache),
            'capacity': self.capacity
        }

    def get_all(self):
        return list(self.cache.items())

    def clear(self):
        self.cache.clear()
        self.hits = 0
        self.misses = 0

class MongoStorage(CacheStorage):
    def __init__(self):
        try:
            import pymongo
            self.client = pymongo.MongoClient(MONGO_URI)
            self.db = self.client[MONGO_DB_NAME]
            self.collection = self.db['dns_cache']
            # Ensure index on key and expiration
            self.collection.create_index([("key", pymongo.ASCENDING)], unique=True)
            self.collection.create_index("timestamp", expireAfterSeconds=DEFAULT_TTL) # Basic TTL, might need refinement
            logger.info("Initialized MongoDB storage")
        except ImportError:
            logger.error("pymongo not installed. Please install it to use MongoDB backend.")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB storage: {e}")
            raise

    def _make_key(self, key):
        return f"{key[0]}:{key[1]}"

    def get(self, key):
        str_key = self._make_key(key)
        try:
            doc = self.collection.find_one({"key": str_key})
            if doc:
                # Check TTL manually if needed, or rely on Mongo's TTL index (which deletes bg)
                # For strict compliance, let's check timestamp
                timestamp = doc['timestamp']
                record = doc['record']
                ttl = record.get('ttl', DEFAULT_TTL)
                if time.time() - timestamp < ttl:
                    return record, timestamp
                else:
                    # Should be cleaned up by Mongo, but if we catch it:
                    self.collection.delete_one({"_id": doc['_id']})
            return None
        except Exception as e:
            logger.error(f"MongoDB get error: {e}")
            return None

    def put(self, key, record):
        str_key = self._make_key(key)
        try:
            self.collection.replace_one(
                {"key": str_key},
                {
                    "key": str_key,
                    "record": record,
                    "timestamp": time.time()
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"MongoDB put error: {e}")

    def get_stats(self):
        try:
            count = self.collection.count_documents({})
            return {'type': 'mongodb', 'size': count}
        except:
            return {'type': 'mongodb', 'error': 'unavailable'}

    def get_all(self):
        try:
            cursor = self.collection.find({})
            results = []
            for doc in cursor:
                # Reconstruct key from string "domain:type" is tricky if domain has colons (IPv6 reverse?)
                # But our _make_key uses "domain:type". 
                # Ideally we should store domain and type separately in Mongo.
                # But for now, let's try to parse the key back or just return the doc's key.
                # The GUI expects key to be (domain, type).
                
                # Let's improve _make_key/put to store separate fields if we want to be robust,
                # but for quick fix, let's split.
                k = doc['key']
                parts = k.rsplit(':', 1) # Split on last colon
                if len(parts) == 2:
                    key = (parts[0], int(parts[1]))
                    value = (doc['record'], doc['timestamp'])
                    results.append((key, value))
            return results
        except Exception as e:
            logger.error(f"MongoDB get_all error: {e}")
            return []

    def clear(self):
        try:
            self.collection.delete_many({})
        except Exception as e:
            logger.error(f"MongoDB clear error: {e}")

class PostgresStorage(CacheStorage):
    def __init__(self):
        try:
            import psycopg2
            self.conn = psycopg2.connect(POSTGRES_URI)
            self.create_table()
            logger.info("Initialized PostgreSQL storage")
        except ImportError:
            logger.error("psycopg2 not installed. Please install it to use PostgreSQL backend.")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL storage: {e}")
            raise

    def create_table(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dns_cache (
                    key TEXT PRIMARY KEY,
                    record BYTEA,
                    timestamp REAL
                )
            """)
            self.conn.commit()

    def _make_key(self, key):
        return f"{key[0]}:{key[1]}"

    def get(self, key):
        str_key = self._make_key(key)
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT record, timestamp FROM dns_cache WHERE key = %s", (str_key,))
                row = cur.fetchone()
                if row:
                    record_bytes, timestamp = row
                    record = pickle.loads(record_bytes)
                    ttl = record.get('ttl', DEFAULT_TTL)
                    if time.time() - timestamp < ttl:
                        return record, timestamp
                    else:
                        # Expired
                        cur.execute("DELETE FROM dns_cache WHERE key = %s", (str_key,))
                        self.conn.commit()
            return None
        except Exception as e:
            logger.error(f"PostgreSQL get error: {e}")
            self.conn.rollback()
            return None

    def put(self, key, record):
        str_key = self._make_key(key)
        record_bytes = pickle.dumps(record)
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO dns_cache (key, record, timestamp)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (key) DO UPDATE
                    SET record = EXCLUDED.record, timestamp = EXCLUDED.timestamp
                """, (str_key, record_bytes, time.time()))
                self.conn.commit()
        except Exception as e:
            logger.error(f"PostgreSQL put error: {e}")
            self.conn.rollback()

    def get_stats(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM dns_cache")
                count = cur.fetchone()[0]
            return {'type': 'postgresql', 'size': count}
        except:
            return {'type': 'postgresql', 'error': 'unavailable'}

    def get_all(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT key, record, timestamp FROM dns_cache")
                rows = cur.fetchall()
                results = []
                for row in rows:
                    k, record_bytes, timestamp = row
                    parts = k.rsplit(':', 1)
                    if len(parts) == 2:
                        key = (parts[0], int(parts[1]))
                        record = pickle.loads(record_bytes)
                        value = (record, timestamp)
                        results.append((key, value))
                return results
        except Exception as e:
            logger.error(f"PostgreSQL get_all error: {e}")
            return []

    def clear(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM dns_cache")
                self.conn.commit()
        except Exception as e:
            logger.error(f"PostgreSQL clear error: {e}")
            self.conn.rollback()
