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
from app.api import auth, master_data, users, comics, comments, likes, history, subscriptions, notifications, analytics, comic_generator, commissions, withdrawals, referrals, worker, comic_requests, downloads, config_app, follows

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
app.include_router(referrals.router, prefix="/api/v1", tags=["Referrals"])
app.include_router(comic_requests.router, prefix="/api/v1", tags=["Comic Requests"])
app.include_router(downloads.router, prefix="/api/v1", tags=["Downloads"])
app.include_router(config_app.router, prefix="/api/v1", tags=["Configs"])
app.include_router(follows.router, prefix="/api/v1", tags=["Follows"])
app.include_router(worker.router, prefix="/tasks", tags=["Worker"])


@app.on_event("startup")
async def startup_event():
    """Run startup tasks including DB schema patching"""
    # 1. Initialize logic
    print("Starting up MamaStoria API...")
    
    # 2. PATCH: Add missing columns to payment_transactions table
    # This is a temporary fix for missing migrations
    try:
        from app.core.database import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            # Add invoice_number if not exists
            conn.execute(text("ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS invoice_number VARCHAR(255)"))
            # Add payment_url if not exists
            conn.execute(text("ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS payment_url TEXT"))
            # Add doku fields if not exists
            conn.execute(text("ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS doku_order_id VARCHAR(255)"))
            conn.execute(text("ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS doku_response TEXT"))
            # Add type_transaction if not exists
            conn.execute(text("ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS type_transaction VARCHAR(255)"))
            # Add expires_at if not exists
            conn.execute(text("ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE"))
            
            # PATCH: Add missing columns to withdrawals table
            conn.execute(text("ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS bank_name VARCHAR(255)"))
            conn.execute(text("ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS account_number VARCHAR(255)"))
            conn.execute(text("ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS account_name VARCHAR(255)"))
            
            # PATCH: Create follows table if not exists
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS follows (
                    id SERIAL PRIMARY KEY,
                    follower_id INTEGER NOT NULL,
                    following_id INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    CONSTRAINT unique_follow UNIQUE (follower_id, following_id),
                    CONSTRAINT fk_follows_follower FOREIGN KEY (follower_id) REFERENCES users(id_users) ON DELETE CASCADE,
                    CONSTRAINT fk_follows_following FOREIGN KEY (following_id) REFERENCES users(id_users) ON DELETE CASCADE
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_follows_id ON follows (id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_follows_follower_id ON follows (follower_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_follows_following_id ON follows (following_id)"))
            
            # PATCH: Create comic_share table if not exists
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS comic_share (
                    id SERIAL PRIMARY KEY,
                    comic_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    CONSTRAINT fk_comic_share_comic FOREIGN KEY (comic_id) REFERENCES comics(id) ON DELETE CASCADE,
                    CONSTRAINT fk_comic_share_user FOREIGN KEY (user_id) REFERENCES users(id_users) ON DELETE CASCADE
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_comic_share_id ON comic_share (id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_comic_share_comic_id ON comic_share (comic_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_comic_share_user_id ON comic_share (user_id)"))
            
            # PATCH: Add total_shares column to comics table
            conn.execute(text("ALTER TABLE comics ADD COLUMN IF NOT EXISTS total_shares BIGINT DEFAULT 0 NOT NULL"))
            
            # Commit changes
            try:
                conn.commit()
                print("Database schema patched successfully (added missing columns to payment_transactions)")
            except Exception:
                # In some configs commit might be auto
                pass
            
    except Exception as e:
        print(f"Database schema patch warning: {e}")
        # Don't inhibit startup, maybe columns exist or DB connection failed


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
