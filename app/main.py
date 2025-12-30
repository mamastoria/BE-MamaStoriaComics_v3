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
    version="2.0.0",
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
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
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
    import os
    from app.core.database import get_database_url, get_engine
    
    # Initialize socket info first
    socket_info = {}
    cloudsql_path = "/cloudsql"
    if os.path.exists(cloudsql_path):
        socket_info["root_exists"] = True
        try:
            instances = os.listdir(cloudsql_path)
            socket_info["instances"] = instances
            
            # Check inside each instance dir
            for instance in instances:
                inst_path = os.path.join(cloudsql_path, instance)
                if os.path.isdir(inst_path):
                    socket_info[f"content_{instance}"] = os.listdir(inst_path)
        except Exception as e:
            socket_info["error"] = str(e)
    else:
        socket_info["root_exists"] = False
        socket_info["path_checked"] = cloudsql_path

    env_vars = {
        "CLOUD_SQL_CONNECTION_NAME": os.environ.get("CLOUD_SQL_CONNECTION_NAME"),
        "INSTANCE_CONNECTION_NAME": os.environ.get("INSTANCE_CONNECTION_NAME"), 
    }

    result = {
        "socket_check": socket_info, # Put this first!
        "env_vars": env_vars,
        "database_url_set": False,
        "database_url_pattern": "",
        "engine_created": False,
        "connection_test": False,
        "error": None
    }
    
    try:
        db_url = get_database_url()
        result["database_url_set"] = bool(db_url)
        if db_url:
            if "@" in db_url:
                prefix = db_url.split("@")[0].split(":")[0] # user
                suffix = db_url.split("@")[1] # host info
                result["database_url_pattern"] = f"{prefix}:***@{suffix}"
            else:
                result["database_url_pattern"] = db_url[:10] + "..."
        
        engine = get_engine()
        result["engine_created"] = engine is not None
        
        # Test actual connection
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
            result["connection_test"] = True
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


# Import routers
from app.api import auth, master_data, users, comics, comments, likes, history, subscriptions, notifications, analytics, comic_generator, commissions, withdrawals

# Include routers
app.include_router(comic_generator.router, tags=["Comic Generator"]) # Mixed paths (api + viewer)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
