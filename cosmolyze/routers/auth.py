"""
routers/auth.py — Authentication Endpoints (Signup & Login with bcrypt + JWT)
"""

import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import APIRouter, HTTPException, status
from models.schemas import SignupRequest, LoginRequest
from services.database import get_database

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_cosmolyze_key_123")

def generate_token(user_id: str) -> str:
    payload = {
        "id": user_id,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected.")
    
    users_col = db["users"]
    email_clean = body.email.strip().lower()
    
    existing = await users_col.find_one({"email": email_clean})
    if existing:
        raise HTTPException(status_code=409, detail="Email is already registered.")
    
    # Hash password
    salt = bcrypt.gensalt(12)
    hashed_pwd = bcrypt.hashpw(body.password.encode('utf-8'), salt).decode('utf-8')
    
    user_doc = {
        "name": body.name.strip(),
        "email": email_clean,
        "password": hashed_pwd,
        "streak_count": 0,
        "last_scan_date": None,
        "createdAt": datetime.utcnow()
    }
    
    result = await users_col.insert_one(user_doc)
    user_id = str(result.inserted_id)
    token = generate_token(user_id)
    
    return {
        "success": True,
        "message": "Account created successfully.",
        "token": token,
        "user": {
            "id": user_id,
            "name": user_doc["name"],
            "email": user_doc["email"]
        }
    }

@router.post("/login")
async def login(body: LoginRequest):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected.")
    
    users_col = db["users"]
    email_clean = body.email.strip().lower()
    
    user = await users_col.find_one({"email": email_clean})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    # Verify password
    stored_hash = user.get("password", "")
    if not bcrypt.checkpw(body.password.encode('utf-8'), stored_hash.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
        
    user_id = str(user["_id"])
    token = generate_token(user_id)
    
    return {
        "success": True,
        "message": "Login successful.",
        "token": token,
        "user": {
            "id": user_id,
            "name": user.get("name", "User"),
            "email": user.get("email", "")
        }
    }
