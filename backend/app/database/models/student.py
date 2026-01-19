# app/database/models/student.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from ..base import Base

class Student(Base):
    __tablename__ = "students"
    
    student_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    iban = Column(String, nullable=False)
    stpt_id = Column(String, nullable=False, unique=True, index=True)
    
    # Relationships
    requests = relationship("Request", back_populates="student", cascade="all, delete-orphan")
    receipts = relationship("Receipt", back_populates="student", cascade="all, delete-orphan")
    documents = relationship("StudentDocument", back_populates="student", cascade="all, delete-orphan")