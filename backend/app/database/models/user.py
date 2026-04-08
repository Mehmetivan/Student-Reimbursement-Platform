# app/database/models/user.py
from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.orm import relationship
from ..base import Base
import enum


class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    account_id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    passwd = Column(String, nullable=False)  # bcrypt hashed
    role = Column(Enum(UserRole), nullable=False, default=UserRole.STUDENT)

    # Relationship to student profile
    student = relationship("Student", back_populates="user", uselist=False)
