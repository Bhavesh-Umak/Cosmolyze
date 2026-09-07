"""
ai_service.py — Cosmolyze Multi-Provider AI Vision & Text Engine (Python)
Supports Google Generative AI (Gemini), Groq, OpenRouter, and OpenAI with robust JSON repair.
"""

import os
import re
import json
import logging
import httpx
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

from .prompts import (
    FACE_ANALYSIS_SYSTEM_PROMPT,
    VERDICT_SYSTEM_PROMPT,
    FORMULA_SYSTEM_PROMPT,
    LIBRARY_SEARCH_SYSTEM_PROMPT,
)

load_dotenv()
logger = logging.getLogger("CosmolyzeAI")

# Try to import google-generativeai
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


FACE_ANALYSIS_FALLBACK = {
    "skin_type": "combination",
    "severity": "mild",
    "zones": ["full face"],
    "detected_concerns": ["General skin assessment"],
    "clinical_observation": "Upon reviewing the localized scan, the skin presents with general surface irregularities. A full analysis requires additional context from your diagnostic questionnaire.",
    "root_causes": [
        {"title": "Surface Layer Build-up", "explanation": "Accumulated dead skin cells and environmental residue can impair the skin barrier and affect overall clarity."},
        {"title": "Hydration Imbalance", "explanation": "Disruption in the skin's natural moisture-retention capacity can exacerbate visible surface concerns."}
    ],
    "recovery_plan": [
        {"title": "STEP 1: LIFESTYLE & HABIT CORRECTION", "details": "Maintain adequate hydration and protect the affected area from unnecessary friction and UV exposure to prevent further aggravation."},
        {"title": "STEP 2: TOPICAL HOME CARE", "details": "Apply specific localized treatments as recommended in the active ingredients section to safely target the root cause of the concern."}
    ],
    "required_actives": [
        {"name": "Niacinamide (10%)", "function": "Regulates sebum production, reduces surface redness, and strengthens the skin barrier over time."},
        {"name": "Hyaluronic Acid (2%)", "function": "Draws moisture into the epidermis to plump and maintain healthy skin hydration levels."}
    ],
    "questions": [
        {
            "id": "q1",
            "question": "What is your primary skin concern right now?",
            "options": ["Active breakouts / acne", "Dryness or flaking", "Oiliness or shine", "Uneven tone or texture"]
        },
        {
            "id": "q2",
            "question": "How sensitive is your skin to new active ingredients?",
            "options": ["Very reactive — burns or stings easily", "Mildly sensitive — occasional redness", "Normal — tolerates most products", "Not sure — never tested actives"]
        },
        {
            "id": "q3",
            "question": "What does your current morning and night skincare routine look like?",
            "options": ["Minimal — just cleanser & moisturiser", "Intermediate — 3–5 targeted products", "Advanced — multiple serums & actives", "No routine at the moment"]
        },
        {
            "id": "q4",
            "question": "Do you have any known ingredient allergies or sensitivities?",
            "options": ["Fragrance or essential oils", "Nuts, seeds or plant extracts", "Acids (AHAs / BHAs / retinol)", "None known"]
        }
    ],
    "_fallback": True
}

VERDICT_FALLBACK = {
    "top_winner": {
        "product_name": "CeraVe Moisturising Cream",
        "brand": "CeraVe",
        "price_inr": 899,
        "mrp_inr": 1099,
        "clinical_match_pct": 88,
        "what_it_is": "A ceramide-rich barrier cream that restores moisture and supports a compromised skin barrier.",
        "key_actives": ["Ceramides 1/3/6-II", "Hyaluronic Acid", "Cholesterol"],
        "key_benefits": ["Barrier repair", "Long-lasting hydration", "Non-comedogenic"],
        "expert_verdict": "A clinically reliable barrier formula suitable as a safe default while a full AI verdict is unavailable.",
        "amazon_url": "https://www.amazon.in/s?k=CeraVe+Moisturising+Cream"
    },
    "alternatives": [
        {
            "product_name": "Cetaphil Gentle Skin Cleanser",
            "brand": "Cetaphil",
            "price_inr": 449,
            "optimal_active": "Mild surfactants for non-stripping cleanse",
            "detected_sensitizer": None,
            "medical_alert": "Low-irritation cleanser; suitable for most sensitive profiles.",
            "match_status": "good",
            "amazon_url": "https://www.amazon.in/s?k=Cetaphil+Gentle+Skin+Cleanser"
        },
        {
            "product_name": "Minimalist 10% Niacinamide Serum",
            "brand": "Minimalist",
            "price_inr": 399,
            "optimal_active": "Niacinamide for barrier support and texture",
            "detected_sensitizer": None,
            "medical_alert": "Introduce slowly if skin is highly reactive.",
            "match_status": "neutral",
            "amazon_url": "https://www.amazon.in/s?k=Minimalist+Niacinamide+10"
        },
        {
            "product_name": "La Roche-Posay Cicaplast Baume B5",
            "brand": "La Roche-Posay",
            "price_inr": 850,
            "optimal_active": "Panthenol + madecassoside for repair",
            "detected_sensitizer": None,
            "medical_alert": "Excellent rescue balm for irritated or recovering skin.",
            "match_status": "good",
            "amazon_url": "https://www.amazon.in/s?k=La+Roche-Posay+Cicaplast+Baume+B5"
        },
        {
            "product_name": "The Ordinary AHA 30% + BHA 2% Peeling Solution",
            "brand": "The Ordinary",
            "price_inr": 790,
            "optimal_active": "High-strength AHA/BHA chemical exfoliation",
            "detected_sensitizer": "Glycolic Acid / Salicylic Acid (high %)",
            "medical_alert": "Potent acids — avoid on compromised, sensitive, or barrier-impaired skin.",
            "match_status": "avoid",
            "amazon_url": "https://www.amazon.in/s?k=The+Ordinary+AHA+30+BHA+2"
        }
    ],
    "_fallback": True
}

FORMULA_FALLBACK = {
    "product_name": "Unknown Product",
    "overall_score": 70,
    "overall_rating": "Fair",
    "summary": "A complete clinical parse was unavailable. Please re-run the analysis for a full ingredient breakdown.",
    "concerns": ["Automated parse incomplete — re-analyse for precise sensitizer detection"],
    "positives": ["Re-submit the ingredient list to receive a full clinical audit"],
    "ingredients": [],
    "_fallback": True
}


def sanitize_ai_json(raw: str, fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Sanitizes LLM outputs to reliably return parsed JSON."""
    if not raw:
        return fallback or {}
    
    text = str(raw).strip()
    
    # Strip markdown code fences
    fenced_match = re.search(r'```(?:json|JSON)?\s*([\s\S]*?)```', text)
    if fenced_match:
        text = fenced_match.group(1).strip()
    else:
        text = re.sub(r'^```(?:json|JSON)?\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```\s*$', '', text)
        text = text.strip()
        
    # Extract outermost JSON braces
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]
        
    # Basic cleanups (smart quotes, trailing commas)
    text = text.replace('\ufeff', '').replace('“', '"').replace('”', '"').replace('’', "'")
    text = re.sub(r',\s*(?=[}\]])', '', text)
    
    try:
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Initial JSON parse failed: {e}. Attempting aggressive bracket repairs.")
        try:
            # Fix unescaped newlines in strings
            cleaned = re.sub(r'(?<!\\)\n', r'\\n', text)
            return json.loads(cleaned)
        except Exception:
            return fallback or {}


def sanitize_questions(raw_questions: Any) -> List[Dict[str, Any]]:
    """Guarantees a clean 4-item questions array for the diagnostic questionnaire."""
    fallback_qs = FACE_ANALYSIS_FALLBACK["questions"]
    if not isinstance(raw_questions, list):
        return fallback_qs
    
    results = []
    for idx, item in enumerate(raw_questions[:4]):
        if isinstance(item, dict):
            qid = item.get("id") or f"q{idx+1}"
            qtext = item.get("question") or item.get("text") or fallback_qs[idx]["question"]
            options = item.get("options")
            if not isinstance(options, list) or len(options) < 2:
                options = fallback_qs[idx]["options"]
            else:
                options = [str(o).strip() for o in options if str(o).strip()][:4]
                while len(options) < 4:
                    options.append("N/A")
            results.append({"id": qid, "question": qtext, "options": options})
        elif isinstance(item, str):
            results.append({
                "id": f"q{idx+1}",
                "question": item.strip() or fallback_qs[idx]["question"],
                "options": fallback_qs[idx]["options"]
            })
            
    while len(results) < 4:
        results.append(fallback_qs[len(results)])
        
    return results[:4]


async def call_gemini_vision(system_prompt: str, user_text: str, image_base64: str) -> str:
    """Calls Google Gemini Vision with system prompt and image."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY_CURRENT") or os.getenv("GEMINI_API_KEY_NEW")
    if not api_key:
        raise ValueError("Gemini API key is not configured in .env")

    # Clean Base64
    mime_type = "image/jpeg"
    b64_data = image_base64
    if "," in image_base64:
        header, b64_data = image_base64.split(",", 1)
        if "png" in header:
            mime_type = "image/png"
        elif "webp" in header:
            mime_type = "image/webp"

    # Direct Gemini REST API call (Fast & reliable without SDK version conflicts)
    model = os.getenv("GEMINI_VISION_MODEL_1") or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{
            "role": "user",
            "parts": [
                {"text": user_text},
                {"inline_data": {"mime_type": mime_type, "data": b64_data}}
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json"
        }
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(endpoint, json=payload)
        if res.status_code != 200:
            raise RuntimeError(f"Gemini API returned status {res.status_code}: {res.text}")
        data = res.json()
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
        if not text:
            raise ValueError("Gemini returned an empty response")
        return text


async def call_groq_text(system_prompt: str, user_text: str) -> str:
    """Calls Groq API for ultra-fast text/formula inference."""
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY_NEW")
    model = os.getenv("GROQ_TEXT_MODEL") or os.getenv("GROQ_TEXT_MODEL_1") or "llama-3.3-70b-versatile"
    
    if not api_key:
        raise ValueError("Groq API key not configured")

    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(endpoint, json=payload, headers={"Authorization": f"Bearer {api_key}"})
        if res.status_code != 200:
            raise RuntimeError(f"Groq API returned status {res.status_code}: {res.text}")
        data = res.json()
        return data["choices"][0]["message"]["content"]


async def call_gemini_text(system_prompt: str, user_text: str) -> str:
    """Calls Gemini API for text-only verdict generation."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY_CURRENT") or os.getenv("GEMINI_API_KEY_NEW")
    if not api_key:
        # Fall back to Groq if Gemini key is absent
        return await call_groq_text(system_prompt, user_text)

    model = os.getenv("GEMINI_TEXT_MODEL_1") or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json"
        }
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(endpoint, json=payload)
        if res.status_code != 200:
            return await call_groq_text(system_prompt, user_text)
        data = res.json()
        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
