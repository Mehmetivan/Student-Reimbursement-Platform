# app/routers/students.py
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..dependencies import get_db, get_current_student
from ..database.models.student import Student
from ..services.student_service import StudentService
from ..services.request_service import RequestService
from ..schemas.student import StudentProfileResponse, ProfileUpdateRequest, DocumentUploadResponse
from ..schemas.request import ReimbursementRequestResponse

router = APIRouter(prefix="/students", tags=["students"])


def validate_upload_file(file: UploadFile) -> None:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(settings.ALLOWED_IMAGE_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"File type '{suffix}' not allowed. Accepted: {allowed}")


def save_temp(file: UploadFile) -> Path:
    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return temp_path


@router.get("/me", response_model=StudentProfileResponse)
def get_my_profile(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    """Get the current student's profile and document upload status."""
    return StudentService.get_profile(db, student)


@router.patch("/me", response_model=StudentProfileResponse)
def update_my_profile(payload: ProfileUpdateRequest, student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    """Update profile fields: name and IBAN."""
    if not payload.name and not payload.iban:
        raise HTTPException(status_code=400, detail="Provide at least name or iban to update")
    return StudentService.update_profile(db=db, student=student, name=payload.name, iban=payload.iban)


@router.post("/me/documents/student-id", response_model=DocumentUploadResponse)
async def upload_student_id(file: UploadFile = File(...), student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    """Upload student ID photo."""
    validate_upload_file(file)
    temp_path = save_temp(file)
    try:
        return StudentService.upload_student_id(db, student, temp_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.post("/me/documents/stpt-card", response_model=DocumentUploadResponse)
async def upload_stpt_card(file: UploadFile = File(...), student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    """Upload STPT card photo. OCR runs immediately to extract the STPT customer ID."""
    validate_upload_file(file)
    temp_path = save_temp(file)
    try:
        return StudentService.upload_stpt_card(db, student, temp_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.post("/me/documents/bank-proof", response_model=DocumentUploadResponse)
async def upload_bank_proof(file: UploadFile = File(...), student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    """Upload bank statement as proof of IBAN."""
    validate_upload_file(file)
    temp_path = save_temp(file)
    try:
        return StudentService.upload_bank_proof(db, student, temp_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.get("/me/requests", response_model=list[ReimbursementRequestResponse])
def get_my_requests(status: Optional[str] = None, student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    """Get all reimbursement requests for the current student."""
    return RequestService.get_student_requests(db=db, student_id=student.student_id, status=status)
