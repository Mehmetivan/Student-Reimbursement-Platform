# app/database/models/user.py
from sqlalchemy import Column, Integer, String, Enum
from ..base import Base
import enum

class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"
    STAFF = "staff"

class User(Base):
    __tablename__ = "users"
    
    account_id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    passwd = Column(String, nullable=False)  # Will store hashed password
    role = Column(Enum(UserRole), nullable=False, default=UserRole.STUDENT)