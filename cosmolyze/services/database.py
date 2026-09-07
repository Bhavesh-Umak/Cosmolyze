"""
database.py — Resilient Multi-Backend Database Adapter for Cosmolyze
Supports MongoDB Atlas (Async Motor) with seamless In-Memory / Local JSON Fallback
so that Authentication, Scans, and Shelf ALWAYS work even without a Mongo URI.
"""

import os
import uuid
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("CosmolyzeDB")

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")

# ── In-Memory Store for Zero-Config Fallback ──────────────────────────────
_memory_store = {
    "users": {},
    "scanresults": [],
    "digitalshelves": {},
    "cachedproducts": {},
}

class MemoryCursor:
    def __init__(self, items):
        self._items = items

    def sort(self, key, direction=-1):
        def sort_key(x):
            v = x.get(key)
            return v if v is not None else ""
        self._items.sort(key=sort_key, reverse=(direction == -1))
        return self

    def limit(self, count):
        self._items = self._items[:count]
        return self

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class FallbackCollection:
    def __init__(self, name: str):
        self.name = name

    async def find_one(self, filter_dict):
        store = _memory_store.get(self.name, {})
        if self.name == "users":
            if "email" in filter_dict:
                target_email = filter_dict["email"].lower()
                for u in store.values():
                    if u.get("email", "").lower() == target_email:
                        return u
            if "_id" in filter_dict:
                return store.get(str(filter_dict["_id"]))
        elif self.name == "digitalshelves":
            uid = str(filter_dict.get("userId"))
            return store.get(uid)
        elif self.name == "cachedproducts":
            pkey = filter_dict.get("productName", "").lower()
            return store.get(pkey)
        return None

    async def insert_one(self, doc):
        new_id = str(uuid.uuid4())
        doc_copy = dict(doc)
        doc_copy["_id"] = new_id
        
        if self.name == "users":
            _memory_store["users"][new_id] = doc_copy
        elif self.name == "scanresults":
            _memory_store["scanresults"].insert(0, doc_copy)
        elif self.name == "digitalshelves":
            _memory_store["digitalshelves"][str(doc_copy.get("userId"))] = doc_copy
        elif self.name == "cachedproducts":
            _memory_store["cachedproducts"][doc_copy.get("productName", "").lower()] = doc_copy

        class InsertResult:
            def __init__(self, inserted_id):
                self.inserted_id = inserted_id
        return InsertResult(new_id)

    async def update_one(self, filter_dict, update_dict, upsert=False):
        set_vals = update_dict.get("$set", {})
        if self.name == "users":
            uid = str(filter_dict.get("_id") or filter_dict.get("id"))
            if uid in _memory_store["users"]:
                _memory_store["users"][uid].update(set_vals)
        elif self.name == "digitalshelves":
            uid = str(filter_dict.get("userId"))
            if uid in _memory_store["digitalshelves"]:
                _memory_store["digitalshelves"][uid].update(set_vals)
            elif upsert:
                doc = {"userId": uid, **set_vals}
                _memory_store["digitalshelves"][uid] = doc
        elif self.name == "cachedproducts":
            pkey = filter_dict.get("productName", "").lower()
            if pkey in _memory_store["cachedproducts"]:
                _memory_store["cachedproducts"][pkey].update(set_vals)
            elif upsert:
                doc = {"productName": pkey, **set_vals}
                _memory_store["cachedproducts"][pkey] = doc

    def find(self, filter_dict):
        if self.name == "scanresults":
            uid = str(filter_dict.get("userId"))
            matched = [dict(s) for s in _memory_store["scanresults"] if str(s.get("userId")) == uid]
            return MemoryCursor(matched)
        return MemoryCursor([])


class FallbackDatabase:
    def __getitem__(self, item: str):
        return FallbackCollection(item)


fallback_db = FallbackDatabase()
client = None
db = None

async def connect_to_mongo():
    global client, db
    if not MONGO_URI:
        logger.info("ℹ️ No MONGODB_URI provided — using high-performance in-memory fallback database.")
        db = fallback_db
        return

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        logger.info("Connecting to MongoDB Atlas...")
        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        db_name = MONGO_URI.rsplit('/', 1)[-1].split('?')[0] or "cosmolyze"
        real_db = client[db_name]
        await real_db.command("ping")
        db = real_db
        logger.info(f"✅ Connected to MongoDB: {db_name}")
    except Exception as e:
        logger.warning(f"⚠️ MongoDB connection failed: {e}. Falling back to embedded in-memory database.")
        db = fallback_db

async def close_mongo_connection():
    global client
    if client:
        client.close()

def get_database():
    global db
    if db is None:
        return fallback_db
    return db
