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


def get_database_url() -> str:
    """Get database URL from environment"""
    url = os.environ.get("DATABASE_URL", "")
    
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
        use_cloud_sql_connector = os.environ.get("USE_CLOUD_SQL_CONNECTOR", "false").lower() == "true"
        connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
        
        if use_cloud_sql_connector and connection_name:
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
                # Fallback to standard URL
                logger.info("Falling back to standard connection string...")
                if not database_url:
                    raise ValueError("DATABASE_URL is not configured")
                _engine = create_engine(database_url, pool_pre_ping=True)
                
        else:
            # Standard connection (Local or Cloud Run with Socket)
            if not database_url:
                raise ValueError("DATABASE_URL is not configured")
            
            logger.info(f"Creating database engine...")
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

