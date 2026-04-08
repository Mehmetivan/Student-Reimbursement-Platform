# app/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from ..dependencies import get_db, require_admin
from ..database.models.user import User
from ..database.models.student import Student, AccountStatus
from ..database.models.request import RequestStatus
from ..services.request_service import RequestService
from ..database.models.student_document import StudentDocument

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Request schemas ───────────────────────────────────────────────────────────

class AccountDecisionRequest(BaseModel):
    decision: str  # "approve" or "reject"
    note: Optional[str] = None


class EditStudentRequest(BaseModel):
    name: Optional[str] = None
    iban: Optional[str] = None
    stpt_id: Optional[str] = None


# ── Student account management ────────────────────────────────────────────────

@router.get("/students")
def list_students(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    List all students. Optionally filter by account_status.
    e.g. GET /admin/students?status=pending_approval
    """
    query = db.query(Student)
    if status:
        try:
            status_enum = AccountStatus(status)
            query = query.filter(Student.account_status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid values: {[s.value for s in AccountStatus]}"
            )
    students = query.all()
    return [
        {
            "student_id": s.student_id,
            "name": s.name,
            "email": s.email,
            "iban": s.iban,
            "stpt_id": s.stpt_id,
            "account_status": s.account_status,
        }
        for s in students
    ]


@router.get("/students/{student_id}")
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Get a single student's full profile including uploaded documents."""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    docs = db.query(StudentDocument).filter(
        StudentDocument.student_id == student_id
    ).all()

    return {
        "student_id": student.student_id,
        "name": student.name,
        "email": student.email,
        "iban": student.iban,
        "stpt_id": student.stpt_id,
        "account_status": student.account_status,
        "documents": [
            {
                "document_id": d.document_id,
                "document_type": d.document_type,
                "file_path": d.file_path,
                "uploaded_at": d.uploaded_at
            }
            for d in docs
        ]
    }


@router.patch("/students/{student_id}/decision")
def decide_student_account(
    student_id: int,
    payload: AccountDecisionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Approve or reject a student account.
    Only students in pending_approval status can be decided on.
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if student.account_status != AccountStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Student is not pending approval (current status: {student.account_status})"
        )

    if payload.decision == "approve":
        student.account_status = AccountStatus.APPROVED
        message = "Student account approved"
    elif payload.decision == "reject":
        student.account_status = AccountStatus.REJECTED
        message = "Student account rejected"
    else:
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")

    db.commit()

    return {
        "message": message,
        "student_id": student_id,
        "new_status": student.account_status,
        "note": payload.note
    }


@router.patch("/students/{student_id}/edit")
def edit_student(
    student_id: int,
    payload: EditStudentRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Edit a student's profile info.
    Useful for correcting OCR errors on stpt_id or fixing typos.
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if payload.name is not None:
        student.name = payload.name
    if payload.iban is not None:
        student.iban = payload.iban
    if payload.stpt_id is not None:
        student.stpt_id = payload.stpt_id

    db.commit()
    db.refresh(student)

    return {
        "message": "Student profile updated",
        "student_id": student_id,
        "name": student.name,
        "iban": student.iban,
        "stpt_id": student.stpt_id
    }


# ── Request management ────────────────────────────────────────────────────────

@router.get("/requests")
def list_requests(
    status: Optional[str] = None,
    timeframe: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    List all reimbursement requests with fraud detection results.

    Filter by status: pending, approved, rejected, under_review
    Filter by timeframe: today, this_week, this_month, 3_months, 6_months, this_year
    """
    return RequestService.get_all_requests(
        db=db,
        status=status,
        timeframe=timeframe
    )


@router.patch("/requests/{request_id}/decision")
def decide_request(
    request_id: int,
    payload: AccountDecisionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Approve, reject, or mark a reimbursement request as under review.
    Optionally include a feedback message for the student.

    decision: "approve", "reject", or "under_review"
    """
    result = RequestService.decide_request(
        db=db,
        request_id=request_id,
        decision=payload.decision,
        feedback=payload.note
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
