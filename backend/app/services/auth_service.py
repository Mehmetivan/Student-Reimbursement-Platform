# app/services/auth_service.py
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models.student import Student, AccountStatus
from ..database.models.user import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:

    # ── Password helpers ──────────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    # ── JWT helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            return None

    # ── Register ──────────────────────────────────────────────────────────────

    @staticmethod
    def register_student(db: Session, email: str, password: str) -> dict:
        """
        Create a User + linked Student record.
        Returns error dict if email already exists.
        """
        if db.query(User).filter(User.email == email).first():
            return {"error": "Email already registered"}

        # Create User (credentials)
        user = User(
            email=email,
            passwd=AuthService.hash_password(password),
            role=UserRole.STUDENT
        )
        db.add(user)
        db.flush()  # get user.account_id without committing yet

        # Create Student (profile — empty for now, filled in Phase 3)
        student = Student(
            user_id=user.account_id,
            email=email,
            account_status=AccountStatus.INCOMPLETE
        )
        db.add(student)
        db.commit()
        db.refresh(user)
        db.refresh(student)

        return {
            "account_id": user.account_id,
            "student_id": student.student_id,
            "email": user.email,
            "role": user.role,
            "account_status": student.account_status
        }

    # ── Login ─────────────────────────────────────────────────────────────────

    @staticmethod
    def login(db: Session, email: str, password: str) -> dict:
        """
        Verify credentials and return a JWT token.
        Returns error dict if credentials are invalid.
        """
        user = db.query(User).filter(User.email == email).first()

        if not user or not AuthService.verify_password(password, user.passwd):
            return {"error": "Invalid email or password"}

        # Build token payload
        payload = {
            "sub": str(user.account_id),
            "email": user.email,
            "role": user.role
        }

        # For students, include student_id in token so we don't need
        # an extra DB query on every protected request
        if user.role == UserRole.STUDENT and user.student:
            payload["student_id"] = user.student.student_id
            payload["account_status"] = user.student.account_status

        token = AuthService.create_access_token(payload)

        return {
            "access_token": token,
            "token_type": "bearer",
            "role": user.role
        }

    # ── Get user from token ───────────────────────────────────────────────────

    @staticmethod
    def get_user_from_token(db: Session, token: str) -> Optional[User]:
        payload = AuthService.decode_token(token)
        if not payload:
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        return db.query(User).filter(User.account_id == int(user_id)).first()
