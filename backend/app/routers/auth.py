# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from ..dependencies import get_db, get_current_user
from ..services.auth_service import AuthService
from ..database.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / Response schemas (local, simple) ────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    account_id: int
    student_id: int
    email: str
    role: str
    account_status: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str


class MeResponse(BaseModel):
    account_id: int
    email: str
    role: str
    student_id: int | None = None
    account_status: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new student account.
    Creates both a User (credentials) and a linked Student (profile).
    Profile fields (name, IBAN, STPT card) are filled in separately in Phase 3.
    """
    result = AuthService.register_student(
        db=db,
        email=payload.email,
        password=payload.password
    )
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    return result


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login with email and password.
    Returns a JWT bearer token.
    Uses OAuth2PasswordRequestForm so it works directly with Swagger UI's
    Authorize button — enter email in the 'username' field.
    """
    result = AuthService.login(
        db=db,
        email=form_data.username,  # OAuth2 form uses 'username' field
        password=form_data.password
    )
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result["error"],
            headers={"WWW-Authenticate": "Bearer"},
        )
    return result


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns the currently authenticated user's info.
    """
    response = {
        "account_id": current_user.account_id,
        "email": current_user.email,
        "role": current_user.role,
    }
    if current_user.student:
        response["student_id"] = current_user.student.student_id
        response["account_status"] = current_user.student.account_status
    return response
