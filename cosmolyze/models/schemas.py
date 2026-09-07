"""
schemas.py — Pydantic Schemas for Cosmolyze API
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field

# ── Auth Schemas ──────────────────────────────────────────
class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    password: str = Field(..., min_length=6)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# ── AI Schemas ────────────────────────────────────────────
class AnalyzeFaceRequest(BaseModel):
    imageBase64: str

class GenerateVerdictRequest(BaseModel):
    answers: List[str] = Field(..., min_items=4, max_items=4)
    budgetMin: Optional[float] = 100.0
    budgetMax: Optional[float] = 3000.0
    faceReport: Optional[Dict[str, Any]] = None
    stage1Report: Optional[Dict[str, Any]] = None

class AnalyzeFormulaRequest(BaseModel):
    productName: Optional[str] = ""
    ingredientList: str = Field(..., min_length=5)

class SearchIngredientRequest(BaseModel):
    query: Optional[str] = None
    q: Optional[str] = None
    search: Optional[str] = None

# ── Scan & Shelf Schemas ──────────────────────────────────
class ProductImageRequest(BaseModel):
    productName: str = Field(..., min_length=2)

class SaveScanRequest(BaseModel):
    concern_category: str
    scan_image_url: Optional[str] = "/images/default-clinical-bottle.png"
    ai_full_json_result: Optional[Dict[str, Any]] = {}

class SaveShelfProductRequest(BaseModel):
    product_name: Optional[str] = None
    productName: Optional[str] = None
    brand: Optional[str] = ""
    price: Optional[float] = 0.0
    price_inr: Optional[float] = 0.0
    imageUrl: Optional[str] = None
    image_url: Optional[str] = None
    amazon_url: Optional[str] = ""
    amazonUrl: Optional[str] = ""
    clinical_match_score: Optional[float] = 0.0
    clinical_match_pct: Optional[float] = 0.0
