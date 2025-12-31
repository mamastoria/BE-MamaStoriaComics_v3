"""
Core configuration settings for MamaStoria API
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # App Config
    APP_NAME: str = "MamaStoria"
    APP_ENV: str = "development"
    SECRET_KEY: str
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
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
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    
    # DOKU Payment
    DOKU_CLIENT_ID: str
    DOKU_SECRET_KEY: str
    DOKU_NOTIFICATION_SECRET: str
    DOKU_IS_PRODUCTION: bool = False
    
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


# Create global settings instance
settings = Settings()
