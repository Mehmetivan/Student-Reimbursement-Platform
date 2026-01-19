# app/database/models/receipt_metadata.py
from sqlalchemy import Column, Integer, String, ForeignKey, Float, JSON, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from ..base import Base

class ReceiptMetadata(Base):
    __tablename__ = "receipt_metadata"
    
    metadata_id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(String, ForeignKey("receipts.receipt_id"), nullable=False, unique=True)
    
    # Layer 2: EXIF Analysis
    exif_status = Column(String, nullable=True)  # "present", "missing", "suspicious"
    has_editing_software = Column(Boolean, default=False)
    timestamp_inconsistency = Column(Boolean, default=False)
    
    # Layer 3: OCR Results
    extracted_receipt_id = Column(String, nullable=True)
    extracted_stpt_id = Column(String, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    
    # Layer 4: Structural Anomaly Detection
    receipt_id_length_anomaly = Column(Boolean, default=False)
    prefix_rarity_score = Column(Float, nullable=True)
    digram_rarity_score = Column(Float, nullable=True)
    
    # Layer 5: Risk Scoring
    tampering_score = Column(Float, nullable=False, default=0.0)
    risk_factors = Column(JSON, nullable=True)  # Store detailed risk breakdown
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    receipt = relationship("Receipt", back_populates="metadata")