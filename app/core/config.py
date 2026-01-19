"""
Core configuration settings for MamaStoria API
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # App Config
    APP_NAME: str = "MamaStoria"
    APP_ENV: str = "development"
    SECRET_KEY: str
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: Optional[str] = None
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days, auto-renewed on use
    
    # Google Cloud
    GOOGLE_PROJECT_ID: str
    GOOGLE_BUCKET_NAME: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    VERTEX_LOCATION: str = "us-central1"
    
    # Firebase
    FIREBASE_CREDENTIALS: Optional[str] = None
    
    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/auth/google/callback"
    
    # Email (Gmail SMTP)
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = "admin@mamastoria.com"
    SMTP_PASSWORD: str = "pzox qhwj dbxb frlm"
    #smtp password: gbog dqwb wzog iral
    
    # DOKU Payment (optional - not all deployments use this)
    DOKU_CLIENT_ID: str = "BRN-0280-1765767732062"
    DOKU_SECRET_KEY: str = "SK-Mb7Lbo9POYkyOCpv1vG2"
    DOKU_NOTIFICATION_SECRET: str = "SK-Mb7Lbo9POYkyOCpv1vG2"
    DOKU_IS_PRODUCTION: bool = True
    USE_MOCK_PAYMENT: bool = True  # Re-enabled because Doku credentials are invalid
    
    # CORS
    CORS_ORIGINS: str = "*"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS_ORIGINS string to list"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        # Ensure local development ports are allowed if DEBUG is True
        if self.DEBUG:
            for dev_origin in ["http://localhost:3000", "http://localhost:5000", "http://localhost:8080", "http://127.0.0.1:3000", "http://127.0.0.1:5000", "http://127.0.0.1:8080"]:
                if dev_origin not in origins:
                    origins.append(dev_origin)
        return origins
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    ALLOWED_IMAGE_EXTENSIONS: str = "jpg,jpeg,png,webp"
    ALLOWED_AUDIO_EXTENSIONS: str = "mp3,wav,m4a"
    
    @property
    def allowed_image_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_IMAGE_EXTENSIONS.split(",")]
    
    @property
    def allowed_audio_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_AUDIO_EXTENSIONS.split(",")]
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Create global settings instance with error handling
try:
    settings = Settings()
except Exception as e:
    import traceback
    import sys
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("CRITICAL CONFIG ERROR - FAILED TO LOAD SETTINGS")
    print(f"Error: {e}")
    traceback.print_exc()
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    
    # Fallback/Dummy settings to prevent container from crashing immediately
    # This allows the app to start so we can see the error logs in Cloud Run
    class DummySettings:
        APP_NAME = "CRASHED_APP"
        APP_ENV = "error"
        SECRET_KEY = "dummy_key_for_startup_investigation"
        DEBUG = True
        DATABASE_URL = None
        JWT_SECRET_KEY = "dummy_jwt_key"
        GOOGLE_PROJECT_ID = "dummy_project_id"
        VERTEX_LOCATION = "us-central1"
        SMTP_SERVER = "localhost"
        SMTP_PORT = 1025
        SMTP_USERNAME = "admin"
        SMTP_PASSWORD = "password"
        DOKU_CLIENT_ID = "dummy"
        DOKU_SECRET_KEY = "dummy"
        DOKU_NOTIFICATION_SECRET = "dummy"
        DOKU_IS_PRODUCTION = False
        USE_MOCK_PAYMENT = True
        CORS_ORIGINS = "*"
        MAX_UPLOAD_SIZE = 10000000
        DEFAULT_PAGE_SIZE = 20
        MAX_PAGE_SIZE = 100
        
        @property
        def cors_origins_list(self):
            return ["*"]
            
        @property
        def allowed_image_extensions_list(self):
            return ["jpg", "png"]
            
        @property
        def allowed_audio_extensions_list(self):
            return ["mp3"]

    settings = DummySettings()
    print("WARNING: USED DUMMY SETTINGS - APP WILL NOT FUNCTION CORRECTLY")
