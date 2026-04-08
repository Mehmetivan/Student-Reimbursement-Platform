# app/dependencies.py
# Reusable FastAPI dependencies for auth and DB access.

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database.session import SessionLocal
from .database.models.user import User, UserRole
from .database.models.student import Student, AccountStatus
from .services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency: extracts and validates the JWT token.
    Injects the current User into any route that depends on it.
    Raises 401 if token is missing, invalid, or expired.
    """
    user = AuthService.get_user_from_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_student(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Student:
    """
    Dependency: ensures the current user is a student and returns their Student record.
    Raises 403 if the user is not a student.
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students only"
        )
    student = db.query(Student).filter(
        Student.user_id == current_user.account_id
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    return student


def get_approved_student(
    student: Student = Depends(get_current_student)
) -> Student:
    """
    Dependency: ensures the student's account is approved before
    they can submit reimbursement requests.
    Raises 403 if account is incomplete, pending, or rejected.
    """
    if student.account_status != AccountStatus.APPROVED:
        messages = {
            AccountStatus.INCOMPLETE: "Please complete your profile before submitting requests",
            AccountStatus.PENDING_APPROVAL: "Your account is pending admin approval",
            AccountStatus.REJECTED: "Your account has been rejected. Please contact support",
        }
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=messages.get(student.account_status, "Account not approved")
        )
    return student


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency: ensures the current user is an admin.
    Raises 403 otherwise.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
