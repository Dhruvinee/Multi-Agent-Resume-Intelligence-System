from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Multi-Agent Resume Intelligence API",
    version="2.0.0",
    description="Multi-Agent AI System for Intelligent Resume Parsing and Skill Matching"
)

# Add CORS middleware - Allow all for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routes
try:
    from api.routes import router
    app.include_router(router, prefix="/api/v1")
    print("✅ Routes loaded successfully from api.routes")
except Exception as e:
    print(f"❌ Error loading routes: {e}")
    # Fallback: Create simple routes directly in main
    @app.get("/api/v1/health")
    async def health_check():
        return {"status": "healthy", "message": "Backend is running"}
    
    @app.get("/api/v1/test")
    async def test():
        return {"message": "API is working"}

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Multi-Agent Resume Intelligence System",
        "version": "2.0.0",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "api_health": "/api/v1/health",
            "api_test": "/api/v1/test"
        }
    }

# Direct health endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00",
        "version": "2.0.0"
    }

if __name__ == "__main__":
    print("🚀 Starting Resume Intelligence System...")
    print("📍 Backend running at: http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )