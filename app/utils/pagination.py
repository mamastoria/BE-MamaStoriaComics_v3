"""
Pagination utilities
"""
from sqlalchemy.orm import Query
from typing import Tuple, List, Any
from app.core.config import settings


def paginate(
    query: Query,
    page: int = 1,
    per_page: int = None
) -> Tuple[List[Any], int]:
    """
    Paginate SQLAlchemy query
    
    Args:
        query: SQLAlchemy query object
        page: Page number (1-indexed)
        per_page: Items per page (defaults to DEFAULT_PAGE_SIZE)
        
    Returns:
        Tuple of (items, total_count)
    """
    if per_page is None:
        per_page = settings.DEFAULT_PAGE_SIZE
    
    # Limit per_page to MAX_PAGE_SIZE
    per_page = min(per_page, settings.MAX_PAGE_SIZE)
    
    # Ensure page is at least 1
    page = max(1, page)
    
    # Get total count
    total = query.count()
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get items
    items = query.limit(per_page).offset(offset).all()
    
    return items, total


def get_pagination_params(
    page: int = 1,
    per_page: int = None
) -> Tuple[int, int]:
    """
    Validate and return pagination parameters
    
    Args:
        page: Page number
        per_page: Items per page
        
    Returns:
        Tuple of (validated_page, validated_per_page)
    """
    if per_page is None:
        per_page = settings.DEFAULT_PAGE_SIZE
    
    # Validate and limit
    page = max(1, page)
    per_page = min(max(1, per_page), settings.MAX_PAGE_SIZE)
    
    return page, per_page
