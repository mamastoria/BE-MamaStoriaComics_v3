"""
Comic Request API endpoints
Manage physical comic orders/requests
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.comic_request import ComicRequest
from app.schemas.comic_request import ComicRequestCreate, ComicRequestResponse
from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response

router = APIRouter()

REQUEST_COST = 20


@router.post("/comic-requests", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_comic_request(
    request_data: ComicRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new physical comic request (Order Souvenir)
    
    - **Cost**: 20,000 credits
    - **recipient_name**: Name of the recipient
    - **phone_number**: Contact number
    - **shipping_address**: Full delivery address
    - **notes**: Additional notes (e.g. comic title)
    """
    # 1. Check if user has enough credits
    if current_user.kredit < REQUEST_COST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient credits. Cost: {REQUEST_COST}, Available: {current_user.kredit}"
        )
    
    # 2. Deduct credits
    current_user.kredit -= REQUEST_COST
    
    # 3. Create request record
    new_request = ComicRequest(
        user_id=current_user.id_users,
        recipient_name=request_data.recipient_name,
        phone_number=request_data.phone_number,
        shipping_address=request_data.shipping_address,
        notes=request_data.notes,
        status="PENDING"
    )
    
    db.add(new_request)
    
    try:
        db.commit()
        db.refresh(new_request)
        db.refresh(current_user)
        
        return {
            "ok": True,
            "message": "Request sent successfully",
            "data": ComicRequestResponse.model_validate(new_request).model_dump(),
            "remaining_credits": current_user.kredit
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process request: {str(e)}"
        )


@router.get("/comic-requests", response_model=dict)
async def list_my_requests(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List user's comic requests history
    """
    query = db.query(ComicRequest).filter(
        ComicRequest.user_id == current_user.id_users
    ).order_by(ComicRequest.created_at.desc())
    
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    data = [ComicRequestResponse.model_validate(item).model_dump() for item in items]
    
    return paginated_response(data, page, per_page, total)
