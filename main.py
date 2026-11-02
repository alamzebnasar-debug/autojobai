"""
Root Entry Point for FastAPI Clean Architecture Application
Run with: uvicorn main:app --reload --port 8000
"""
from presentation.fastapi_app import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
