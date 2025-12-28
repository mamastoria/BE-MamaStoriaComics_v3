"""
MamaStoria Comics API - FastAPI Application
Converted from Laravel PHP to Python FastAPI
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="API untuk platform pembuatan komik dengan AI",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
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


# Import routers
from app.api import auth, master_data, users, comics, comments, likes, history, subscriptions, notifications, analytics

# Include routers
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(master_data.router, prefix="/api/v1", tags=["Master Data"])
app.include_router(comics.router, prefix="/api/v1", tags=["Comics"])
app.include_router(comments.router, prefix="/api/v1", tags=["Comments"])
app.include_router(likes.router, prefix="/api/v1", tags=["Likes"])
app.include_router(history.router, prefix="/api/v1", tags=["History"])
app.include_router(subscriptions.router, prefix="/api/v1", tags=["Subscriptions"])
app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])
app.include_router(analytics.router, prefix="/api", tags=["Analytics"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
