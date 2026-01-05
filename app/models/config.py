
from sqlalchemy import Column, Integer, String, Text
from app.core.database import Base

class Config(Base):
    """
    Config model for system settings
    """
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True)
    name_config = Column(String(255), nullable=False)
    value_config = Column(Text, nullable=True)
