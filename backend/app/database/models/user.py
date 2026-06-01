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


"""

python -c "
from app.database.base import Base
from app.database.models.user import User, UserRole
from app.database.models.student import Student
from app.database.models.request import Request
from app.database.models.receipt import Receipt
from app.database.models.student_document import StudentDocument
from app.database.models.receipt_metadata import ReceiptMetadata
from app.database.models.receipt_ocr import ReceiptOCR
from app.database.models.receipt_anomalies import ReceiptAnomalies
from app.database.models.receipt_risk_assessment import ReceiptRiskAssessment
from app.database.session import SessionLocal
from app.services.auth_service import AuthService

db = SessionLocal()
admin = User(
    email='admin@test.com',
    passwd=AuthService.hash_password('admin123'),
    role=UserRole.ADMIN
)
db.add(admin)
db.commit()
print('Admin created: admin@test.com / admin123')
db.close()
"


"""