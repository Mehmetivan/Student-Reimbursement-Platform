# app/database/models/receipt_risk_assessment.py
from sqlalchemy import Column, Integer, String, ForeignKey, Float, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from ..base import Base

class ReceiptRiskAssessment(Base):
    __tablename__ = "receipt_risk_assessment"
    
    assessment_id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(String, ForeignKey("receipts.receipt_id"), nullable=False, unique=True)
    
    # Combined Risk Scoring (Layer 5)
    total_risk_score = Column(Float, nullable=False, default=0.0)
    assessment = Column(String, nullable=True)
    
    # Detailed Risk Breakdown
    risk_factors = Column(JSON, nullable=True)
    
    # Individual Layer Scores
    layer1_risk = Column(Float, default=0.0)
    layer2_risk = Column(Float, default=0.0)
    layer3_risk = Column(Float, default=0.0)
    layer4_risk = Column(Float, default=0.0)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    receipt = relationship("Receipt", back_populates="risk_assessment")