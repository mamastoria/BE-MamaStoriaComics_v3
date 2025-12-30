"""
FastAPI dependencies for authentication and authorization
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from JWT token
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Decode token
    payload = decode_token(token)
    if not payload:
        # Check if it was because of subject type
        try:
             # Try decoding without verification to see if sub is int
             import jwt as pyjwt
             # Note: We are using python-jose, but let's see.
             # Actually, let's just modify the error handling in decode_token to be more permissive or fix the creation.
             pass
        except:
             pass
             
        print(f"Token validation failed: Payload is None for token: {token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user ID from payload
    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        print(f"Token validation failed: User ID (sub) missing in payload: {payload}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Query user from database
    try:
        # JWT subject should be a string, but DB ID is int. 
        # Convert to int to be safe (handles "1" -> 1).
        uid_int = int(user_id)
        user = db.query(User).filter(User.id_users == uid_int).first()
    except ValueError:
         print(f"Token validation failed: User ID {user_id} is not a valid integer")
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"Database error in get_current_user: {str(e)}")
        # We don't want to expose DB errors to client, but we must log them
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication error"
        )

    if user is None:
        print(f"Token validation failed: User ID {user_id} not found in database")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is verified
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not verified"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current active user
    Can be extended to check if user is active/banned
    """
    return current_user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to get optional user (for endpoints that work with or without auth)
    Returns None if no token provided or token is invalid
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload:
        return None
    
    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        return None
    
    try:
        # Cast to int to ensure correct type for DB query (Postgres strict typing)
        uid_int = int(user_id)
        user = db.query(User).filter(User.id_users == uid_int).first()
        return user
    except ValueError:
        # Invalid ID format
        return None
    except Exception as e:
        print(f"Error in get_optional_user: {e}")
        return None
