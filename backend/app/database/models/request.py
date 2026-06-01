# app/database/models/request.py
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from ..base import Base
import enum

class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Request(Base):
    __tablename__ = "requests"

    request_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=False)
    comment = Column(Text, nullable=True)
    status = Column(Enum(RequestStatus), nullable=False, default=RequestStatus.PENDING)
    submit_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    review_timestamp = Column(DateTime, nullable=True)
    admin_feedback = Column(Text, nullable=True)

    # Confirmation — admin cannot see request until student confirms
    confirmed = Column(Boolean, nullable=False, default=False)

    # Resubmission tracking
    resubmission_count = Column(Integer, nullable=False, default=0)
    last_resubmit_timestamp = Column(DateTime, nullable=True)

    # Relationships
    student = relationship("Student", back_populates="requests")
    receipts = relationship("Receipt", back_populates="request", cascade="all, delete-orphan")
