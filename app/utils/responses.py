"""
Utility functions for API responses
"""
from typing import Any, Optional, List, Dict
from fastapi import status
from fastapi.responses import JSONResponse
from app.schemas.common import PaginationMeta


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    status_code: int = status.HTTP_200_OK
) -> JSONResponse:
    """
    Create success response
    
    Args:
        data: Response data
        message: Optional success message
        status_code: HTTP status code
        
    Returns:
        JSONResponse object
    """
    response = {"ok": True}
    
    if message:
        response["message"] = message
    
    if data is not None:
        response["data"] = data
    
    return JSONResponse(content=response, status_code=status_code)


def error_response(
    error: str,
    detail: Optional[str] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST
) -> JSONResponse:
    """
    Create error response
    
    Args:
        error: Error message
        detail: Optional error details
        status_code: HTTP status code
        
    Returns:
        JSONResponse object
    """
    response = {
        "ok": False,
        "error": error
    }
    
    if detail:
        response["detail"] = detail
    
    return JSONResponse(content=response, status_code=status_code)


def paginated_response(
    data: List[Any],
    page: int,
    per_page: int,
    total: int
) -> Dict:
    """
    Create paginated response
    
    Args:
        data: List of items
        page: Current page number
        per_page: Items per page
        total: Total number of items
        
    Returns:
        Dict with data and pagination meta
    """
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    meta = PaginationMeta(
        current_page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )
    
    return {
        "ok": True,
        "data": data,
        "meta": meta.model_dump()
    }
