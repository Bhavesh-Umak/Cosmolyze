"""
routers/ai.py — Cosmolyze AI Vision, Computer Vision, & Verdict Generation (FastAPI)
"""

import logging
from fastapi import APIRouter, HTTPException, status
from models.schemas import (
    AnalyzeFaceRequest,
    GenerateVerdictRequest,
    AnalyzeFormulaRequest,
    SearchIngredientRequest,
)
from services.prompts import (
    FACE_ANALYSIS_SYSTEM_PROMPT,
    VERDICT_SYSTEM_PROMPT,
    FORMULA_SYSTEM_PROMPT,
    LIBRARY_SEARCH_SYSTEM_PROMPT,
)
from services.cv_analyzer import analyze_skin_features
from services.ai_service import (
    call_gemini_vision,
    call_gemini_text,
    call_groq_text,
    sanitize_ai_json,
    sanitize_questions,
    FACE_ANALYSIS_FALLBACK,
    VERDICT_FALLBACK,
    FORMULA_FALLBACK,
)

logger = logging.getLogger("CosmolyzeAI_Router")
router = APIRouter(prefix="/api/ai", tags=["AI Clinical Engine"])


@router.post("/analyze-face")
async def analyze_face(body: AnalyzeFaceRequest):
    """
    Stage 1: AI Vision Diagnostic + OpenCV Skin Biomarker Analysis
    """
    image_b64 = body.imageBase64
    if not image_b64 or not image_b64.startswith("data:image/"):
        raise HTTPException(
            status_code=400,
            detail="imageBase64 is required and must be a valid image data URI."
        )

    # 1. Extract Computer Vision Biomarkers with OpenCV
    cv_metrics = analyze_skin_features(image_b64)

    # 2. Augment user prompt with real CV telemetry
    user_prompt = (
        f"Please analyze this patient face image and generate the 4 personalised diagnostic questions. "
        f"Clinical Image Telemetry: Erythema Redness Index: {cv_metrics.get('erythema_index', 'N/A')}, "
        f"Texture Profile: {cv_metrics.get('texture_roughness', 'N/A')}."
    )

    try:
        # Call Gemini Vision (with automatic fallback)
        raw_ai_text = await call_gemini_vision(
            system_prompt=FACE_ANALYSIS_SYSTEM_PROMPT,
            user_text=user_prompt,
            image_base64=image_b64
        )
        parsed = sanitize_ai_json(raw_ai_text, fallback=FACE_ANALYSIS_FALLBACK)
    except Exception as e:
        logger.error(f"Gemini Vision failed: {e}. Utilizing fallback schema.")
        parsed = {**FACE_ANALYSIS_FALLBACK, "_fallback": True}

    # Format output fields
    questions = sanitize_questions(parsed.get("questions"))
    concerns = parsed.get("detected_concerns")
    if not isinstance(concerns, list):
        concerns = ["Clinical skin evaluation"]

    response_data = {
        "skin_type": parsed.get("skin_type_assessment") or parsed.get("skin_type") or FACE_ANALYSIS_FALLBACK["skin_type"],
        "severity": parsed.get("severity_level") or parsed.get("severity") or FACE_ANALYSIS_FALLBACK["severity"],
        "zones": parsed.get("affected_zones") or parsed.get("zones") or FACE_ANALYSIS_FALLBACK["zones"],
        "detected_concerns": concerns,
        "clinical_observation": parsed.get("clinical_observation") or FACE_ANALYSIS_FALLBACK["clinical_observation"],
        "root_causes": parsed.get("root_causes") or FACE_ANALYSIS_FALLBACK["root_causes"],
        "recovery_plan": parsed.get("recovery_plan") or FACE_ANALYSIS_FALLBACK["recovery_plan"],
        "required_actives": parsed.get("required_actives") or FACE_ANALYSIS_FALLBACK["required_actives"],
        "questions": questions,
        "cv_telemetry": cv_metrics,  # Real Computer Vision features for competition presentation
    }

    if parsed.get("_fallback"):
        response_data["fallback"] = True

    return {"success": True, "data": response_data}


@router.post("/generate-verdict")
async def generate_verdict(body: GenerateVerdictRequest):
    """
    Stage 2: Formulator Verdict & Routine Recommendations (Text-Only)
    """
    report = body.faceReport or body.stage1Report or {}
    clinical_obs = report.get("clinical_observation", "Not available")
    
    actives = report.get("required_actives", [])
    actives_text = "\n".join([f"{a.get('name')}: {a.get('function')}" for a in actives if isinstance(a, dict)]) or "Not available"
    
    concerns = report.get("detected_concerns", [])
    concerns_text = ", ".join(concerns) if isinstance(concerns, list) else "Not available"

    user_text = f"""
STAGE 1 CLINICAL REPORT SUMMARY:
- Detected Concerns: {concerns_text}
- Clinical Observation: {clinical_obs}
- Required Active Ingredients:
{actives_text}

Patient Diagnostic Questionnaire Responses:
1. {body.answers[0] if len(body.answers) > 0 else 'N/A'}
2. {body.answers[1] if len(body.answers) > 1 else 'N/A'}
3. {body.answers[2] if len(body.answers) > 2 else 'N/A'}
4. {body.answers[3] if len(body.answers) > 3 else 'N/A'}

Patient Budget Range: ₹{body.budgetMin} – ₹{body.budgetMax} INR

Using ONLY the Stage 1 report and answers above, formulate the clinical verdict JSON (top_winner + exactly 4 alternatives).
""".strip()

    try:
        raw_text = await call_gemini_text(VERDICT_SYSTEM_PROMPT, user_text)
        parsed = sanitize_ai_json(raw_text, fallback=VERDICT_FALLBACK)
    except Exception as e:
        logger.error(f"Verdict generation failed: {e}. Utilizing fallback schema.")
        parsed = {**VERDICT_FALLBACK, "_fallback": True}

    if not parsed.get("top_winner") or not isinstance(parsed.get("alternatives"), list):
        parsed = {**VERDICT_FALLBACK, "_fallback": True}

    return {"success": True, "data": parsed}


@router.post("/analyze-formula")
async def analyze_formula(body: AnalyzeFormulaRequest):
    """
    Analyzes cosmetic ingredient list safety, comedogenicity, and active mechanisms.
    """
    user_text = f"Product Name: {body.productName or 'Unknown Product'}\nIngredient List:\n{body.ingredientList.strip()}"
    try:
        raw = await call_groq_text(FORMULA_SYSTEM_PROMPT, user_text)
        parsed = sanitize_ai_json(raw, fallback=FORMULA_FALLBACK)
    except Exception as e:
        logger.warning(f"Formula parse via Groq failed: {e}")
        parsed = {**FORMULA_FALLBACK, "product_name": body.productName or "Unknown Product"}

    return {"success": True, "data": parsed}


@router.post("/search-ingredient")
async def search_ingredient(body: SearchIngredientRequest):
    """
    Searches cosmetic ingredient database / AI library.
    """
    query = (body.query or body.q or body.search or "").strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters.")

    user_text = f"Ingredient Library search tokens: '{query}'"
    try:
        raw = await call_groq_text(LIBRARY_SEARCH_SYSTEM_PROMPT, user_text)
        parsed = sanitize_ai_json(raw, fallback={"ingredients": []})
    except Exception as e:
        logger.warning(f"Ingredient lookup failed: {e}")
        parsed = {"ingredients": []}

    ingredients = parsed.get("ingredients", [])
    return {"success": True, "data": {"query": query, "ingredients": ingredients}}
