"""
Root main.py proxy to cosmolyze/main.py for Render and other cloud platforms
"""

import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
COSMOLYZE_DIR = os.path.join(CURRENT_DIR, "cosmolyze")

if COSMOLYZE_DIR not in sys.path:
    sys.path.insert(0, COSMOLYZE_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from cosmolyze.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
