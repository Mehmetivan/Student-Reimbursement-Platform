# app/database/models/receipt.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from ..base import Base

class Receipt(Base):
    __tablename__ = "receipts"
    
    receipt_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=False)
    request_id = Column(Integer, ForeignKey("requests.request_id"), nullable=False)
    file_path = Column(String, nullable=False)
    
    # Layer 1: File Integrity
    sha256_hash = Column(String(64), nullable=False, index=True)
    
    # Relationships to other tables
    student = relationship("Student", back_populates="receipts")
    request = relationship("Request", back_populates="receipts")
    
    # Fraud Detection Data (separate tables)
    receipt_metadata = relationship("ReceiptMetadata", back_populates="receipt", uselist=False, cascade="all, delete-orphan")  # Changed from exif_data
    ocr_data = relationship("ReceiptOCR", back_populates="receipt", uselist=False, cascade="all, delete-orphan")
    anomaly_data = relationship("ReceiptAnomalies", back_populates="receipt", uselist=False, cascade="all, delete-orphan")
    risk_assessment = relationship("ReceiptRiskAssessment", back_populates="receipt", uselist=False, cascade="all, delete-orphan")