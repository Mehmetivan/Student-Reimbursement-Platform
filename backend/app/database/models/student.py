# app/database/models/student.py
from sqlalchemy import Column, Integer, String, Enum, ForeignKey
from sqlalchemy.orm import relationship
from ..base import Base
import enum


class AccountStatus(str, enum.Enum):
    INCOMPLETE = "incomplete"         # just registered, profile not filled
    PENDING_APPROVAL = "pending_approval"  # profile complete, waiting for admin
    APPROVED = "approved"             # admin approved, can submit requests
    REJECTED = "rejected"             # admin rejected


class Student(Base):
    __tablename__ = "students"

    student_id = Column(Integer, primary_key=True, index=True)

    # Link to User (auth credentials)
    user_id = Column(Integer, ForeignKey("users.account_id"), nullable=False, unique=True)

    # Profile fields — nullable because filled in Phase 3 after registration
    name = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=False, index=True)  # duplicated from User for convenience
    iban = Column(String, nullable=True)
    stpt_id = Column(String, nullable=True, unique=True, index=True)

    # Account status gate
    account_status = Column(
        Enum(AccountStatus),
        nullable=False,
        default=AccountStatus.INCOMPLETE
    )

    # Relationships
    user = relationship("User", back_populates="student")
    requests = relationship("Request", back_populates="student", cascade="all, delete-orphan")
    receipts = relationship("Receipt", back_populates="student", cascade="all, delete-orphan")
    documents = relationship("StudentDocument", back_populates="student", cascade="all, delete-orphan")
