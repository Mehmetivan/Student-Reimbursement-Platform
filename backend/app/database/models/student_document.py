# app/database/models/student_document.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from ..base import Base

class DocumentType(str, enum.Enum):
    STUDENT_ID = "STUDENT_ID"
    STPT_CARD = "STPT_CARD"
    BANK_PROOF = "BANK_PROOF"

class StudentDocument(Base):
    __tablename__ = "student_documents"
    
    document_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    student = relationship("Student", back_populates="documents")