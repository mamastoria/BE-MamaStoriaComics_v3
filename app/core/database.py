"""
Database configuration and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Optional
import os
import logging

logger = logging.getLogger(__name__)

# Create Base class for models
Base = declarative_base()

# Lazy initialization for engine and session
_engine = None
_SessionLocal = None


def _is_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"true", "1", "yes", "y", "on"}


def get_database_url() -> str:
    """Get database URL from environment"""
    url = os.environ.get("DATABASE_URL", "")
    
    # If using Cloud SQL Connector, we still allow DATABASE_URL for credential extraction
    use_cloud_sql_connector = _is_truthy(os.environ.get("USE_CLOUD_SQL_CONNECTOR"))
    if use_cloud_sql_connector:
        # Return whatever is set so connector code can parse user/pass/db
        # The engine creation will not use this URL when connector mode is enabled
        if not url:
            try:
                from app.core.config import settings
                url = settings.DATABASE_URL
            except Exception as e:
                logger.warning(f"Could not load DATABASE_URL from settings (connector mode): {e}")
                url = ""
        return url
    
    if not url:
        # Try to import from settings as fallback
        try:
            from app.core.config import settings
            url = settings.DATABASE_URL
        except Exception as e:
            logger.warning(f"Could not load DATABASE_URL from settings: {e}")
            url = ""
    
    return url


def get_engine():
    """Get or create SQLAlchemy engine lazily"""
    global _engine
    
    if _engine is None:
        database_url = get_database_url()
        
        # Check if we should use Cloud SQL Connector (set via env var in Cloud Run)
        use_cloud_sql_connector = _is_truthy(os.environ.get("USE_CLOUD_SQL_CONNECTOR"))
        connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
        
        if use_cloud_sql_connector:
            if not connection_name:
                raise ValueError("USE_CLOUD_SQL_CONNECTOR=true but CLOUD_SQL_CONNECTION_NAME is not set.")
            logger.info("Using Cloud SQL Python Connector...")
            try:
                from google.cloud.sql.connector import Connector, IPTypes
                import pg8000
                
                # Initialize connector
                connector = Connector()
                
                # Get DB config from env
                db_user = os.environ.get("DB_USER", "postgres")
                db_pass = os.environ.get("DB_PASS", "") # Should be provided if using connector
                db_name = os.environ.get("DB_NAME", "nanobanana_db")
                
                # Extract user/pass/db from DATABASE_URL if available and DB_PASS not set
                if not db_pass and database_url:
                    try:
                        from sqlalchemy.engine.url import make_url
                        u = make_url(database_url)
                        db_user = u.username or db_user
                        db_pass = u.password or db_pass
                        db_name = u.database or db_name
                    except:
                        pass
                        
                # FIX: Handle potential double-percent escaping in password from .env
                if db_pass and "%%" in db_pass:
                    logger.info("Detected '%%' in DB password, replacing with '%'")
                    db_pass = db_pass.replace("%%", "%")

                def getconn():
                    conn = connector.connect(
                        connection_name,
                        "pg8000",
                        user=db_user,
                        password=db_pass,
                        db=db_name,
                        ip_type=IPTypes.PUBLIC, # Use public IP
                    )
                    return conn
                
                _engine = create_engine(
                    "postgresql+pg8000://",
                    creator=getconn,
                    pool_pre_ping=True, 
                    pool_size=5,
                    max_overflow=10,
                    echo=os.environ.get("DEBUG", "false").lower() == "true",
                )
                logger.info("Cloud SQL Connector engine created successfully")
                
            except Exception as e:
                logger.error(f"Failed to create Cloud SQL Connector engine: {e}")
                # Don't fallback to socket-based URL - it won't work in Cloud Run
                # Raise error instead so deployment fails (forces fix)
                raise RuntimeError(
                    f"Cloud SQL Connector failed: {e}. "
                    "Check: USE_CLOUD_SQL_CONNECTOR=true, CLOUD_SQL_CONNECTION_NAME, DB_PASS, "
                    "Cloud SQL Admin API enabled, and service account permissions."
                )
                
        else:
            # Standard connection (Local or Cloud Run with Socket)
            database_url = get_database_url()
            
            if not database_url:
                raise ValueError(
                    "DATABASE_URL not configured and USE_CLOUD_SQL_CONNECTOR is false. "
                    "Either set DATABASE_URL (without /cloudsql path) or enable Cloud SQL Connector."
                )
            
            # Prevent socket-based URLs in Cloud Run (they won't work without Auth Proxy)
            if "/cloudsql/" in database_url:
                logger.error(
                    "Socket-based DATABASE_URL detected in standard mode. "
                    "Enable Cloud SQL Connector instead: USE_CLOUD_SQL_CONNECTOR=true"
                )
                raise ValueError(
                    "Socket-based DATABASE_URL requires Cloud SQL Connector. "
                    "Set USE_CLOUD_SQL_CONNECTOR=true"
                )
            logger.info(f"Database URL pattern: {database_url[:50]}...")
            
            try:
                _engine = create_engine(
                    database_url,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10,
                    pool_timeout=30,
                    pool_recycle=1800,  # Recycle connections after 30 min
                    echo=os.environ.get("DEBUG", "false").lower() == "true",
                )
                logger.info("Database engine created successfully")
            except Exception as e:
                logger.error(f"Failed to create database engine: {e}")
                raise
    
    return _engine


def get_session_local():
    """Get or create SessionLocal lazily"""
    global _SessionLocal
    
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=get_engine()
        )
    
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    Use this in FastAPI route dependencies.
    
    Example:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


# For backward compatibility
def init_db():
    """Initialize database - creates tables if needed"""
    try:
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

