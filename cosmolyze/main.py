"""
main.py — Cosmolyze AI Vision & Dermatology Platform (FastAPI Backend)
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

from services.database import connect_to_mongo, close_mongo_connection
from routers import auth, ai, scan, shelf

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()

app = FastAPI(
    title="Cosmolyze AI API",
    description="Clinical-Grade AI & Computer Vision Cosmetic Formulation & Dermatological Analysis Platform",
    version="2.0.0",
    lifespan=lifespan
)

# ── CORS Middleware ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include Routers ──────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(scan.router)
app.include_router(shelf.router)

# ── API Health Check ─────────────────────────────────────────────────────────
@app.get("/api")
async def api_health():
    return {
        "success": True,
        "message": "🚀 Cosmolyze Python (FastAPI + OpenCV + Gemini AI) API is running.",
        "version": "2.0.0"
    }

# ── Mount Static Images ──────────────────────────────────────────────────────
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
images_dir = os.path.join(CURRENT_DIR, "images")
if os.path.exists(images_dir):
    app.mount("/images", StaticFiles(directory=images_dir), name="images")

# ── Serve Frontend SPA (index.html) ──────────────────────────────────────────
@app.get("/")
async def serve_home():
    index_file = os.path.join(CURRENT_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Cosmolyze API Running. index.html not found."}

@app.middleware("http")
async def spa_fallback_middleware(request: Request, call_next):
    response = await call_next(request)
    if response.status_code == 404 and not request.url.path.startswith("/api") and not request.url.path.startswith("/docs") and not request.url.path.startswith("/openapi.json"):
        index_file = os.path.join(CURRENT_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
