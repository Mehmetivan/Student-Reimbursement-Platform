# app/database/models/receipt_ocr.py
from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from ..base import Base

class ReceiptOCR(Base):
    __tablename__ = "receipt_ocr"
    
    ocr_id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(String, ForeignKey("receipts.receipt_id"), nullable=False, unique=True)
    
    # OCR Engine Used
    ocr_engine_used = Column(String, nullable=True)
    
    # Extracted Data
    extracted_receipt_id = Column(String, nullable=True)
    extracted_stpt_id = Column(String, nullable=True)
    
    # Validation Results
    stpt_id_matches_student = Column(Boolean, nullable=True)
    expected_stpt_id = Column(String, nullable=True)
    
    # Confidence Scores
    ocr_confidence = Column(Float, nullable=True)
    stpt_id_confidence = Column(Float, nullable=True)
    receipt_id_confidence = Column(Float, nullable=True)
    
    # Raw OCR Text (optional - for debugging)
    raw_ocr_text = Column(Text, nullable=True)
    
    # Layer 3 Risk Score
    layer3_risk_score = Column(Float, default=0.0)
    
    # OCR Flags
    ocr_flags = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    receipt = relationship("Receipt", back_populates="ocr_data")