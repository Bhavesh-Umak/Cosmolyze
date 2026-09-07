"""
routers/shelf.py — User Digital Shelf & Bookmarking (FastAPI)
"""

import urllib.parse
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from models.schemas import SaveShelfProductRequest
from middleware.auth_py import get_current_user_id
from services.database import get_database

router = APIRouter(prefix="/api/shelf", tags=["Digital Shelf"])
FALLBACK_IMAGE = "/images/default-clinical-bottle.png"

@router.get("/")
async def get_shelf(user_id: str = Depends(get_current_user_id)):
    """
    Returns saved products on the user's shelf.
    """
    db = get_database()
    if db is None:
        return {"success": True, "data": {"products": []}}
        
    shelf = await db["digitalshelves"].find_one({"userId": user_id})
    products = shelf.get("saved_products", []) if shelf else []
    
    # Ensure imageUrl key is present
    for p in products:
        p["imageUrl"] = p.get("imageUrl") or p.get("image_url") or FALLBACK_IMAGE
        
    return {"success": True, "data": {"products": products}}


@router.post("/save", status_code=status.HTTP_201_CREATED)
async def save_to_shelf(body: SaveShelfProductRequest, user_id: str = Depends(get_current_user_id)):
    """
    Adds or updates a product on the user's shelf.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected.")
        
    p_name = (body.product_name or body.productName or "").strip()
    if len(p_name) < 2:
        raise HTTPException(status_code=400, detail="product_name is required.")
        
    product_item = {
        "product_name": p_name,
        "brand": body.brand or "",
        "price": body.price or body.price_inr or 0.0,
        "imageUrl": body.imageUrl or body.image_url or FALLBACK_IMAGE,
        "amazon_url": body.amazon_url or body.amazonUrl or "",
        "clinical_match_score": body.clinical_match_score or body.clinical_match_pct or 0.0,
        "added_at": datetime.utcnow().isoformat()
    }
    
    shelf = await db["digitalshelves"].find_one({"userId": user_id})
    if not shelf:
        await db["digitalshelves"].insert_one({
            "userId": user_id,
            "saved_products": [product_item]
        })
    else:
        existing = shelf.get("saved_products", [])
        updated = [p for p in existing if p.get("product_name", "").lower() != p_name.lower()]
        updated.insert(0, product_item)
        await db["digitalshelves"].update_one(
            {"userId": user_id},
            {"$set": {"saved_products": updated}}
        )
        
    return {
        "success": True,
        "message": "Product saved to My Digital Shelf.",
        "data": {"product": product_item}
    }


@router.delete("/{name}")
async def delete_from_shelf(name: str, user_id: str = Depends(get_current_user_id)):
    """
    Deletes a product by name from user's shelf.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected.")
        
    decoded_name = urllib.parse.unquote(name).strip().lower()
    shelf = await db["digitalshelves"].find_one({"userId": user_id})
    if not shelf:
        raise HTTPException(status_code=404, detail="Shelf not found.")
        
    products = shelf.get("saved_products", [])
    filtered = [p for p in products if p.get("product_name", "").lower() != decoded_name]
    
    if len(filtered) == len(products):
        raise HTTPException(status_code=404, detail="Product not found on shelf.")
        
    await db["digitalshelves"].update_one(
        {"userId": user_id},
        {"$set": {"saved_products": filtered}}
    )
    
    return {"success": True, "message": "Product removed from shelf."}
