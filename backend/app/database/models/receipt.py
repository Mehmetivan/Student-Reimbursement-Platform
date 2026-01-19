# app/database/models/receipt.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from ..base import Base

class Receipt(Base):
    __tablename__ = "receipts"
    
    receipt_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=False)
    request_id = Column(Integer, ForeignKey("requests.request_id"), nullable=False)
    file_path = Column(String, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    
    # Relationships
    student = relationship("Student", back_populates="receipts")
    request = relationship("Request", back_populates="receipts")
    receipt_metadata = relationship("ReceiptMetadata", back_populates="receipt", uselist=False, cascade="all, delete-orphan")