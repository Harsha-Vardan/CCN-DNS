import unittest
import time
from dns_resolver.storage import MemoryStorage, MongoStorage, PostgresStorage
from dns_resolver.config import CACHE_SIZE

class TestStorage(unittest.TestCase):
    def test_memory_storage(self):
        storage = MemoryStorage(capacity=2)
        
        # Test Put/Get
        key1 = ('example.com', 'A')
        record1 = {'data': '1.2.3.4', 'ttl': 100}
        storage.put(key1, record1)
        
        result = storage.get(key1)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], record1)
        
        # Test Capacity
        key2 = ('google.com', 'A')
        record2 = {'data': '8.8.8.8', 'ttl': 100}
        storage.put(key2, record2)
        
        key3 = ('facebook.com', 'A')
        record3 = {'data': '3.3.3.3', 'ttl': 100}
        storage.put(key3, record3)
        
        # key1 should be evicted (LRU)
        self.assertIsNone(storage.get(key1))
        self.assertIsNotNone(storage.get(key2))
        self.assertIsNotNone(storage.get(key3))

        # Test get_all
        all_items = storage.get_all()
        self.assertEqual(len(all_items), 2)
        keys = [item[0] for item in all_items]
        self.assertIn(key2, keys)
        self.assertIn(key3, keys)

        # Test clear
        storage.clear()
        self.assertEqual(len(storage.get_all()), 0)
        self.assertEqual(storage.get_stats()['size'], 0)

    def test_memory_expiration(self):
        storage = MemoryStorage()
        key = ('expired.com', 'A')
        record = {'data': '1.1.1.1', 'ttl': 0.1}
        storage.put(key, record)
        
        time.sleep(0.2)
        self.assertIsNone(storage.get(key))

if __name__ == '__main__':
    unittest.main()
