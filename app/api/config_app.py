
"""
Config API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.config_app import Config

router = APIRouter()

@router.get("/config/{name_config}", response_model=dict)
async def get_config_by_name(
    name_config: str,
    db: Session = Depends(get_db)
):
    """
    Get configuration value by name
    """
    config = db.query(Config).filter(Config.name_config == name_config).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config '{name_config}' not found"
        )
    
    return {
        "ok": True,
        "data": {
            "id": config.id,
            "name_config": config.name_config,
            "value_config": config.value_config
        }
    }
