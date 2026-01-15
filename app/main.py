"""
MamaStoria Comics API - FastAPI Application
Converted from Laravel PHP to Python FastAPI
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from app.core.config import settings

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="API untuk platform pembuatan komik dengan AI",
    version="2.0.1",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Global Exception Handler to ensure CORS headers are always present on 500 errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_detail = f"Global Error: {str(exc)}"
    print(error_detail) # Log to console/cloud logging
    traceback.print_exc()
    
    # Get origin for safe CORS
    origin = request.headers.get("origin", "*")
    
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": "Internal Server Error", "detail": error_detail},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://mamastoria.com"
    ],
    allow_origin_regex="https://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/debug-root")
async def debug_root():
    return {"ok": True, "message": "Root debugging works"}

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - health check"""
    return {
        "ok": True,
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": "2.0.0",
        "environment": settings.APP_ENV
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV
    }


@app.get("/health/db", tags=["Health"])
async def db_health_check():
    """Database connection health check"""
    from app.core.database import get_engine
    from sqlalchemy import text
    
    result = {
        "status": "unknown",
        "error": None
    }
    
    try:
        engine = get_engine()
        # Test actual connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            result["status"] = "connected"
            
    except Exception as e:
        result["status"] = "disconnected"
        result["error"] = str(e)
    
    return result


# Import routers
from app.api import auth, master_data, users, comics, comments, likes, history, subscriptions, notifications, analytics, comic_generator, commissions, withdrawals, referrals, worker, comic_requests, downloads, config_app, follows, public, admin, jobs

# Include routers
app.include_router(admin.setup_router, tags=["Setup"])  # NO AUTH - for initial setup
app.include_router(comic_generator.router, tags=["Comic Generator"]) # Mixed paths (api + viewer)
app.include_router(public.router, prefix="/api/v1/public", tags=["Public"]) # Public endpoints without auth
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1", tags=["Users"])
app.include_router(master_data.router, prefix="/api/v1", tags=["Master Data"])
app.include_router(history.router, prefix="/api/v1", tags=["History"])
app.include_router(comics.router, prefix="/api/v1", tags=["Comics"])
app.include_router(comments.router, prefix="/api/v1", tags=["Comments"])
app.include_router(likes.router, prefix="/api/v1", tags=["Likes"])
app.include_router(subscriptions.router, prefix="/api/v1", tags=["Subscriptions"])
app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])
app.include_router(commissions.router, prefix="/api/v1", tags=["Commissions"])
app.include_router(withdrawals.router, prefix="/api/v1", tags=["Withdrawals"])
app.include_router(referrals.router, prefix="/api/v1", tags=["Referrals"])
app.include_router(comic_requests.router, prefix="/api/v1", tags=["Comic Requests"])
app.include_router(downloads.router, prefix="/api/v1", tags=["Downloads"])
app.include_router(config_app.router, prefix="/api/v1", tags=["Configs"])
app.include_router(follows.router, prefix="/api/v1", tags=["Follows"])
app.include_router(worker.router, prefix="/tasks", tags=["Worker"])
app.include_router(jobs.router, tags=["Job Queue"])  # Database-driven job queue
app.include_router(admin.router, tags=["Admin"])  # Admin endpoints with prefix in router


@app.on_event("startup")
async def startup_event():
    """Run startup tasks including DB schema patching"""
    print("Starting up MamaStoria API...")
    
    # Note: Database migrations are now handled by scripts/migrate_job_queue_columns.py
    # Run that script to add new columns to the database
    
    print("Application startup event finished.")


# Mount static files at the END of all route definitions
from pathlib import Path
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    print(f"✓ Static files mounted from {static_dir}")
else:
    print(f"⚠ Static directory not found: {static_dir}")


if __name__ == "__main__":
    import uvicorn
    import os
    # Get port from env (default 8080 for Cloud Run)
    port = int(os.environ.get("PORT", 8080))
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
