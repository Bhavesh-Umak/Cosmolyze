"""
routers/auth.py — Universal Frictionless Authentication (Instant Demo Mode)
Allows ANY email/password combination to log in or signup instantly with a valid JWT token.
"""

import os
import uuid
import jwt
from datetime import datetime, timedelta
from fastapi import APIRouter, status
from models.schemas import SignupRequest, LoginRequest
from services.database import get_database

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_cosmolyze_key_123_universal_demo")

def generate_token(user_id: str) -> str:
    payload = {
        "id": user_id,
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def derive_name_from_email(email: str, default: str = "User") -> str:
    if "@" in email:
        return email.split("@")[0].replace(".", " ").title()
    return default or "User"

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest):
    """
    Universal Signup: Always succeeds. If account exists, logs in seamlessly.
    """
    db = get_database()
    email_clean = (body.email or "demo@cosmolyze.app").strip().lower()
    name_clean = (body.name or derive_name_from_email(email_clean)).strip()
    
    user = None
    if db is not None:
        try:
            user = await db["users"].find_one({"email": email_clean})
        except Exception:
            user = None

    if not user:
        user_id = str(uuid.uuid4())
        user_doc = {
            "_id": user_id,
            "name": name_clean,
            "email": email_clean,
            "streak_count": 1,
            "last_scan_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "createdAt": datetime.utcnow()
        }
        if db is not None:
            try:
                await db["users"].insert_one(user_doc)
            except Exception:
                pass
    else:
        user_id = str(user.get("_id") or user.get("id") or uuid.uuid4())
        name_clean = user.get("name") or name_clean

    token = generate_token(user_id)
    return {
        "success": True,
        "message": "Welcome! Account ready.",
        "token": token,
        "user": {
            "id": user_id,
            "name": name_clean,
            "email": email_clean
        }
    }

@router.post("/login")
async def login(body: LoginRequest):
    """
    Universal Login: Always succeeds with ANY credentials!
    If user is not in DB, auto-creates session instantly.
    """
    db = get_database()
    email_clean = (body.email or "user@cosmolyze.app").strip().lower()
    name_clean = derive_name_from_email(email_clean, "Clinical User")
    
    user = None
    if db is not None:
        try:
            user = await db["users"].find_one({"email": email_clean})
        except Exception:
            user = None

    if user:
        user_id = str(user.get("_id") or user.get("id") or uuid.uuid4())
        name_clean = user.get("name") or name_clean
    else:
        # Auto-create user on the fly so login never fails
        user_id = str(uuid.uuid4())
        user_doc = {
            "_id": user_id,
            "name": name_clean,
            "email": email_clean,
            "streak_count": 1,
            "last_scan_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "createdAt": datetime.utcnow()
        }
        if db is not None:
            try:
                await db["users"].insert_one(user_doc)
            except Exception:
                pass

    token = generate_token(user_id)
    return {
        "success": True,
        "message": "Login successful.",
        "token": token,
        "user": {
            "id": user_id,
            "name": name_clean,
            "email": email_clean
        }
    }
