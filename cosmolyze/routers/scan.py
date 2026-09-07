"""
routers/scan.py — Scan Persistence, History & High-Definition Product Image Scraper
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

# High-Resolution Real Product Image Catalog for Top Skincare Brands
CURATED_PRODUCT_IMAGES = {
    "cerave moisturising cream": "https://m.media-amazon.com/images/I/61s8B7b4FvL._SL1500_.jpg",
    "cerave": "https://m.media-amazon.com/images/I/61s8B7b4FvL._SL1500_.jpg",
    "cetaphil gentle skin cleanser": "https://m.media-amazon.com/images/I/61Vd1q1858L._SL1500_.jpg",
    "cetaphil": "https://m.media-amazon.com/images/I/61Vd1q1858L._SL1500_.jpg",
    "minimalist 10% niacinamide": "https://m.media-amazon.com/images/I/61u3y8uLp-L._SL1500_.jpg",
    "minimalist 2% salicylic acid": "https://m.media-amazon.com/images/I/61D7aW8Y31L._SL1500_.jpg",
    "minimalist": "https://m.media-amazon.com/images/I/61u3y8uLp-L._SL1500_.jpg",
    "the ordinary aha 30%": "https://m.media-amazon.com/images/I/51r265vU28L._SL1200_.jpg",
    "the ordinary niacinamide": "https://m.media-amazon.com/images/I/61A3zUuK7cL._SL1500_.jpg",
    "the ordinary": "https://m.media-amazon.com/images/I/61A3zUuK7cL._SL1500_.jpg",
    "la roche-posay cicaplast": "https://m.media-amazon.com/images/I/61qGz9k2E0L._SL1500_.jpg",
    "la roche-posay": "https://m.media-amazon.com/images/I/61qGz9k2E0L._SL1500_.jpg",
    "neutrogena hydro boost": "https://m.media-amazon.com/images/I/61YhT224kAL._SL1500_.jpg",
    "neutrogena": "https://m.media-amazon.com/images/I/61YhT224kAL._SL1500_.jpg",
    "derma co": "https://m.media-amazon.com/images/I/51qB7gV-06L._SL1200_.jpg",
    "cosrx snail mucin": "https://m.media-amazon.com/images/I/61u5Tf2m8pL._SL1500_.jpg",
    "cosrx": "https://m.media-amazon.com/images/I/61u5Tf2m8pL._SL1500_.jpg",
    "dot & key": "https://m.media-amazon.com/images/I/61nN3YJ5GzL._SL1500_.jpg",
    "dr. sheth": "https://m.media-amazon.com/images/I/61mN67e6u3L._SL1500_.jpg",
    "plum": "https://m.media-amazon.com/images/I/61z9p5k4f4L._SL1500_.jpg",
    "bioderma": "https://m.media-amazon.com/images/I/61p-E2h8L-L._SL1500_.jpg"
}

# Reliable HD Skincare Bottle Fallback Image
FALLBACK_IMAGE = "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=600&auto=format&fit=crop&q=80"

async def fetch_ddg_image(product_name: str) -> Optional[str]:
    """Fetches product bottle image from DuckDuckGo safely."""
    try:
        query = f"{product_name} product bottle skincare"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://duckduckgo.com/",
        }
        
        async with httpx.AsyncClient(timeout=8.0) as client:
            token_res = await client.get(f"https://duckduckgo.com/?q={query}", headers=headers)
            vqd_match = re.search(r'vqd=["\']([^"\']+)["\']', token_res.text) or re.search(r'vqd=([\d-]+)&', token_res.text)
            if not vqd_match:
                return None
            vqd = vqd_match.group(1)
            
            i_url = f"https://duckduckgo.com/i.js?l=us-en&o=json&q={query}&vqd={vqd}&p=1"
            img_res = await client.get(i_url, headers=headers)
            if img_res.status_code == 200:
                data = img_res.json()
                results = data.get("results", [])
                for item in results:
                    img_cand = item.get("image") or item.get("thumbnail") or item.get("url")
                    if img_cand and img_cand.startswith("http") and not any(bad in img_cand.lower() for bad in ["gif", "svg", "logo"]):
                        return img_cand
    except Exception as e:
        logger.warning(f"DuckDuckGo image scrape notice: {e}")
    return None


@router.post("/product-image")
async def get_product_image(body: ProductImageRequest):
    """
    Returns high-definition live image URL for any cosmetic/skincare product.
    """
    db = get_database()
    prod_key = body.productName.strip().lower()
    
    # 1. Match against curated HD product catalog
    for key, img_url in CURATED_PRODUCT_IMAGES.items():
        if key in prod_key or prod_key in key:
            return {"success": True, "imageUrl": img_url, "fromCache": True}

    # 2. Check Database Cache
    if db is not None:
        try:
            cached = await db["cachedproducts"].find_one({"productName": prod_key})
            if cached and cached.get("imageUrl") and cached.get("imageUrl").startswith("http"):
                return {"success": True, "imageUrl": cached["imageUrl"], "fromCache": True}
        except Exception:
            pass
            
    # 3. Live search lookup
    live_img = await fetch_ddg_image(body.productName)
    final_img = live_img or FALLBACK_IMAGE
    
    # 4. Cache resolved image
    if db is not None:
        try:
            await db["cachedproducts"].update_one(
                {"productName": prod_key},
                {"$set": {"productName": prod_key, "imageUrl": final_img}},
                upsert=True
            )
        except Exception:
            pass
        
    return {"success": True, "imageUrl": final_img, "fromCache": False}


@router.post("/save", status_code=status.HTTP_201_CREATED)
async def save_scan(body: SaveScanRequest, user_id: str = Depends(get_current_user_id)):
    """
    Saves a scan result and updates user daily scan streak.
    """
    db = get_database()
    scan_doc = {
        "userId": user_id,
        "concern_category": body.concern_category or "Clinical Skin Analysis",
        "scan_image_url": body.scan_image_url or FALLBACK_IMAGE,
        "ai_full_json_result": body.ai_full_json_result or {},
        "createdAt": datetime.utcnow()
    }
    
    res = await db["scanresults"].insert_one(scan_doc)
    
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
            "id": str(getattr(res, "inserted_id", "")),
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
    streak = user.get("streak_count", 1) if user else 1
    
    return {
        "success": True,
        "data": {
            "scans": scans,
            "streak_count": streak
        }
    }
