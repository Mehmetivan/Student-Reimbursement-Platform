# app/routers/receipts.py
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session
from typing import Optional

from ..config import settings
from ..dependencies import get_db, get_approved_student
from ..database.models.student import Student
from ..database.models.request import Request
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
    comment: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    student: Student = Depends(get_approved_student)
):
    """
    Submit a receipt for reimbursement.
    Runs all 5 fraud detection layers and saves results.
    Request stays unconfirmed until student reviews and confirms.
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
            student_id=student.student_id,
            filename=file.filename,
            comment=comment
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.patch("/resubmit/{request_id}")
async def resubmit_receipt(
    request_id: int,
    file: UploadFile = File(...),
    comment: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    student: Student = Depends(get_approved_student)
):
    """
    Replace the receipt on an unconfirmed request.
    Only allowed while the request has not been confirmed yet.
    """
    validate_upload_file(file)

    request = db.query(Request).filter(
        Request.request_id == request_id,
        Request.student_id == student.student_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Cannot resubmit — request has already been confirmed and sent to admin."
        )

    if request.status.value != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resubmit — request has already been {request.status.value}."
        )

    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Delete old receipt files
        for old_receipt in request.receipts:
            old_file = Path(old_receipt.file_path)
            if old_file.exists():
                old_file.unlink()

        # Clear old receipts from database
        for old_receipt in request.receipts:
            db.delete(old_receipt)
        db.flush()

        if comment is not None:
            request.comment = comment

        request.resubmission_count += 1
        request.last_resubmit_timestamp = datetime.utcnow()
        db.commit()

        return await ReceiptService.run_full_pipeline(
            db=db,
            file_path=temp_path,
            student_id=student.student_id,
            filename=file.filename,
            comment=comment,
            existing_request_id=request_id
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.patch("/confirm/{request_id}")
def confirm_receipt(
    request_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_approved_student)
):
    """
    Student confirms their submission — makes it visible to admin.
    Cannot be undone.
    """
    request = db.query(Request).filter(
        Request.request_id == request_id,
        Request.student_id == student.student_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.confirmed:
        raise HTTPException(status_code=400, detail="Request already confirmed.")

    if request.status.value != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm — request has already been {request.status.value}."
        )

    request.confirmed = True
    db.commit()

    return {"message": "Request confirmed and submitted to admin for review.", "request_id": request_id}
