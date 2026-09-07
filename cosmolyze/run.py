import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n=======================================================")
    print(f"🚀 Starting Cosmolyze Python FastAPI Server on port {port}")
    print(f"📄 Frontend:  http://localhost:{port}/")
    print(f"📚 API Docs:  http://localhost:{port}/docs")
    print(f"🔗 API Base:  http://localhost:{port}/api")
    print(f"=======================================================\n")
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)
