from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection

from app.config import settings


@lru_cache
def get_client() -> MongoClient:
    # One client per process: it keeps its own connection pool.
    return MongoClient(settings.mongo_url, serverSelectionTimeoutMS=3000, tz_aware=True)


def get_collection() -> Collection:
    return get_client()[settings.mongo_db]["notifications"]


def ensure_indexes(collection: Collection) -> None:
    collection.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    collection.create_index([("channel", ASCENDING)])
