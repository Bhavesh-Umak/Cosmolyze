"""
routers/scan.py — Scan Persistence, History & Product Image Scraper (FastAPI)
"""

import logging
import httpx
import re
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from models.schemas import ProductImageRequest, SaveScanRequest
from middleware.auth_py import get_current_user_id
from services.database import get_database

logger = logging.getLogger("CosmolyzeScan")
router = APIRouter(prefix="/api/scan", tags=["Scans & Imagery"])

FALLBACK_IMAGE = "/images/default-clinical-bottle.png"

async def fetch_ddg_image(product_name: str) -> Optional[str]:
    """Fetches product bottle image from DuckDuckGo safely."""
    try:
        query = f"{product_name} product packaging bottle"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://duckduckgo.com/",
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Get VQD token
            token_res = await client.get(f"https://duckduckgo.com/?q={query}", headers=headers)
            vqd_match = re.search(r'vqd=["\']([^"\']+)["\']', token_res.text) or re.search(r'vqd=([\d-]+)&', token_res.text)
            if not vqd_match:
                return None
            vqd = vqd_match.group(1)
            
            # 2. Search images
            i_url = f"https://duckduckgo.com/i.js?l=us-en&o=json&q={query}&vqd={vqd}&p=1"
            img_res = await client.get(i_url, headers=headers)
            if img_res.status_code == 200:
                data = img_res.json()
                results = data.get("results", [])
                for item in results:
                    img_cand = item.get("image") or item.get("thumbnail") or item.get("url")
                    if img_cand and img_cand.startswith("http"):
                        return img_cand
    except Exception as e:
        logger.warning(f"DuckDuckGo image scrape exception: {e}")
    return None


@router.post("/product-image")
async def get_product_image(body: ProductImageRequest):
    """
    Returns live image URL for a product (with MongoDB caching).
    """
    db = get_database()
    prod_key = body.productName.strip().lower()
    
    if db is not None:
        cached = await db["cachedproducts"].find_one({"productName": prod_key})
        if cached and cached.get("imageUrl") and not cached.get("imageUrl").endswith(FALLBACK_IMAGE):
            return {"success": True, "imageUrl": cached["imageUrl"], "fromCache": True}
            
    # Live lookup
    live_img = await fetch_ddg_image(body.productName)
    final_img = live_img or FALLBACK_IMAGE
    
    if db is not None:
        await db["cachedproducts"].update_one(
            {"productName": prod_key},
            {"$set": {"productName": prod_key, "imageUrl": final_img}},
            upsert=True
        )
        
    return {"success": True, "imageUrl": final_img, "fromCache": False}


@router.post("/save", status_code=status.HTTP_201_CREATED)
async def save_scan(body: SaveScanRequest, user_id: str = Depends(get_current_user_id)):
    """
    Saves a scan result and updates user daily scan streak.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected.")
        
    scan_doc = {
        "userId": user_id,
        "concern_category": body.concern_category or "Clinical Skin Analysis",
        "scan_image_url": body.scan_image_url or FALLBACK_IMAGE,
        "ai_full_json_result": body.ai_full_json_result or {},
        "createdAt": datetime.utcnow()
    }
    
    res = await db["scanresults"].insert_one(scan_doc)
    
    # Update user streak
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    user = await db["users"].find_one({"_id": user_id}) or await db["users"].find_one({"id": user_id})
    
    if user:
        last_date = user.get("last_scan_date")
        if last_date != today_str:
            yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
            new_streak = (user.get("streak_count", 0) + 1) if last_date == yesterday_str else 1
            await db["users"].update_one(
                {"_id": user["_id"]},
                {"$set": {"streak_count": new_streak, "last_scan_date": today_str}}
            )

    return {
        "success": True,
        "message": "Scan result saved successfully.",
        "data": {
            "id": str(res.inserted_id),
            "concern_category": scan_doc["concern_category"],
            "scan_image_url": scan_doc["scan_image_url"],
            "created_at": scan_doc["createdAt"].isoformat()
        }
    }


@router.get("/history")
async def get_scan_history(user_id: str = Depends(get_current_user_id)):
    """
    Returns last 20 scans for the logged-in user.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected.")
        
    cursor = db["scanresults"].find({"userId": user_id}).sort("createdAt", -1).limit(20)
    scans = []
    async for doc in cursor:
        scans.append({
            "concern_category": doc.get("concern_category", "Clinical Skin Analysis"),
            "scan_image_url": doc.get("scan_image_url", FALLBACK_IMAGE),
            "ai_full_json_result": doc.get("ai_full_json_result", {}),
            "createdAt": doc.get("createdAt").isoformat() if isinstance(doc.get("createdAt"), datetime) else doc.get("createdAt")
        })
        
    user = await db["users"].find_one({"_id": user_id}) or await db["users"].find_one({"id": user_id})
    streak = user.get("streak_count", 0) if user else 0
    
    return {
        "success": True,
        "data": {
            "scans": scans,
            "streak_count": streak
        }
    }
