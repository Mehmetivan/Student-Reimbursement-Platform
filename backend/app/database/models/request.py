# app/database/models/request.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from ..base import Base
import enum

class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_REVIEW = "under_review"

class Request(Base):
    __tablename__ = "requests"
    
    request_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=False)
    comment = Column(Text, nullable=True)
    status = Column(Enum(RequestStatus), nullable=False, default=RequestStatus.PENDING)
    submit_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    review_timestamp = Column(DateTime, nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="requests")
    receipts = relationship("Receipt", back_populates="request", cascade="all, delete-orphan")