# app/routers/receipts.py
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..dependencies import get_db, get_approved_student
from ..database.models.student import Student
from ..services.receipt_service import ReceiptService

router = APIRouter(prefix="/receipts", tags=["receipts"])


def validate_upload_file(file: UploadFile) -> None:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(settings.ALLOWED_IMAGE_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"File type '{suffix}' not allowed. Accepted: {allowed}"
        )


@router.post("/submit")
async def submit_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    student: Student = Depends(get_approved_student)  # JWT auth + approval check
):
    """
    Submit a receipt for reimbursement.
    Requires a valid JWT token and an approved student account.
    Runs all 5 fraud detection layers and returns the assessment result.
    """
    validate_upload_file(file)

    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return await ReceiptService.run_full_pipeline(
            db=db,
            file_path=temp_path,
            student_id=student.student_id,  # comes from JWT, not query param
            filename=file.filename
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
