import pymongo
from dns_resolver.config import MONGO_URI

try:
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.server_info() # Trigger connection
    print("MongoDB Connection Successful")
except Exception as e:
    print(f"MongoDB Connection Failed: {e}")
