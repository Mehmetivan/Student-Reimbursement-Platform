# app/database/models/receipt_anomalies.py
from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from ..base import Base

class ReceiptAnomalies(Base):
    __tablename__ = "receipt_anomalies"
    
    anomaly_id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(String, ForeignKey("receipts.receipt_id"), nullable=False, unique=True)
    
    # Structural Anomaly Detection (Layer 4)
    receipt_id_length_anomaly = Column(Boolean, default=False)
    prefix_rarity_score = Column(Float, nullable=True)
    digram_rarity_score = Column(Float, nullable=True)
    
    # Layer 4 Risk Score
    layer4_risk_score = Column(Float, default=0.0)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    receipt = relationship("Receipt", back_populates="anomaly_data")