"""
database.py — Async MongoDB Connection & Collections for Cosmolyze
"""

import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("CosmolyzeDB")

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or "mongodb://localhost:27017/cosmolyze"

client: AsyncIOMotorClient = None
db = None

async def connect_to_mongo():
    global client, db
    try:
        logger.info(f"Connecting to MongoDB...")
        client = AsyncIOMotorClient(MONGO_URI)
        db_name = MONGO_URI.rsplit('/', 1)[-1].split('?')[0] or "cosmolyze"
        db = client[db_name]
        # Quick ping
        await db.command("ping")
        logger.info(f"✅ Successfully connected to MongoDB database: {db_name}")
    except Exception as e:
        logger.error(f"❌ MongoDB connection error: {e}")

async def close_mongo_connection():
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed.")

def get_database():
    return db
