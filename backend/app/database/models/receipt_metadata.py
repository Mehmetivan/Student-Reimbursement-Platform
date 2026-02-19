# app/database/models/receipt_metadata.py
from sqlalchemy import Column, Integer, String, ForeignKey, Float, JSON, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from ..base import Base

class ReceiptMetadata(Base):
    __tablename__ = "receipt_metadata"
    
    metadata_id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(String, ForeignKey("receipts.receipt_id"), nullable=False, unique=True)
    
    # Layer 2: EXIF Analysis (Enhanced)
    exif_status = Column(String, nullable=True)  # "present", "missing", "incomplete"
    has_editing_software = Column(Boolean, default=False)
    editing_software_name = Column(String, nullable=True)  # Name of detected software
    is_mobile_camera = Column(Boolean, nullable=True)
    camera_model = Column(String, nullable=True)
    photo_age_days = Column(Integer, nullable=True)
    has_exif_inconsistencies = Column(Boolean, default=False)
    exif_flags = Column(JSON, nullable=True)  # List of EXIF-related flags
    layer2_risk_score = Column(Float, default=0.0)
    timestamp_inconsistency = Column(Boolean, default=False)  # Deprecated but kept for compatibility
    
    # Layer 3: OCR Results
    extracted_receipt_id = Column(String, nullable=True)
    extracted_stpt_id = Column(String, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    layer3_risk_score = Column(Float, default=0.0)
    
    # Layer 4: Structural Anomaly Detection
    receipt_id_length_anomaly = Column(Boolean, default=False)
    prefix_rarity_score = Column(Float, nullable=True)
    digram_rarity_score = Column(Float, nullable=True)
    layer4_risk_score = Column(Float, default=0.0)
    
    # Layer 5: Combined Risk Scoring
    tampering_score = Column(Float, nullable=False, default=0.0)  # Overall risk (0.0 - 1.0)
    risk_factors = Column(JSON, nullable=True)  # Detailed breakdown of all risk factors
    assessment = Column(String, nullable=True)  # "low_risk", "medium_risk", "high_risk"
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    receipt = relationship("Receipt", back_populates="receipt_metadata")