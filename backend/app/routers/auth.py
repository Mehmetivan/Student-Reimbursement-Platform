# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..schemas.auth import RegisterRequest, RegisterResponse, LoginResponse, MeResponse, ChangePasswordRequest

from ..dependencies import get_db, get_current_user
from ..services.auth_service import AuthService
from ..database.models.user import User
from ..schemas.auth import RegisterRequest, RegisterResponse, LoginResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new student account."""
    result = AuthService.register_student(db=db, email=payload.email, password=payload.password)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return result


@router.post("/login", response_model=LoginResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login with email and password. Returns a JWT bearer token."""
    result = AuthService.login(db=db, email=form_data.username, password=form_data.password)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=result["error"], headers={"WWW-Authenticate": "Bearer"})
    return result


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns the currently authenticated user's info."""
    response = {"account_id": current_user.account_id, "email": current_user.email, "role": current_user.role}
    if current_user.student:
        response["student_id"] = current_user.student.student_id
        response["account_status"] = current_user.student.account_status
    return response

@router.patch("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change the authenticated user's password."""
    if not AuthService.verify_password(payload.current_password, current_user.passwd):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters"
        )
    current_user.passwd = AuthService.hash_password(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully"}
