# app/database/models/receipt_metadata.py
from sqlalchemy import Column, Integer, String, ForeignKey, Float, JSON, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from ..base import Base

class ReceiptMetadata(Base):
    __tablename__ = "receipt_metadata"
    
    exif_id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(String, ForeignKey("receipts.receipt_id"), nullable=False, unique=True)
    
    # EXIF Analysis Results (Layer 2)
    exif_status = Column(String, nullable=True)
    has_editing_software = Column(Boolean, default=False)
    editing_software_name = Column(String, nullable=True)
    is_mobile_camera = Column(Boolean, nullable=True)
    camera_model = Column(String, nullable=True)
    photo_age_days = Column(Integer, nullable=True)
    has_exif_inconsistencies = Column(Boolean, default=False)
    exif_flags = Column(JSON, nullable=True)
    
    # Layer 2 Risk Score
    layer2_risk_score = Column(Float, default=0.0)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    receipt = relationship("Receipt", back_populates="receipt_metadata")