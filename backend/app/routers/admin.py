# app/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from ..dependencies import get_db, require_admin
from ..database.models.user import User
from ..database.models.student import Student, AccountStatus
from ..database.models.student_document import StudentDocument
from ..services.request_service import RequestService
from ..schemas.student import StudentDetailResponse, AccountDecisionRequest, AccountDecisionResponse, AdminEditStudentRequest
from ..schemas.request import ReimbursementRequestResponse, RequestDecisionRequest

router = APIRouter(prefix="/admin", tags=["admin"])


def _format_student(student, docs):
    return {
        "student_id": student.student_id,
        "name": student.name,
        "email": student.email,
        "iban": student.iban,
        "stpt_id": student.stpt_id,
        "account_status": student.account_status,
        "documents": [
            {"document_id": d.document_id, "document_type": d.document_type,
             "file_path": d.file_path, "uploaded_at": str(d.uploaded_at)}
            for d in docs
        ]
    }


@router.get("/students", response_model=list[StudentDetailResponse])
def list_students(status: Optional[str] = None, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """List all students, optionally filtered by account_status."""
    query = db.query(Student)
    if status:
        try:
            query = query.filter(Student.account_status == AccountStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {[s.value for s in AccountStatus]}")
    students = query.all()
    return [_format_student(s, db.query(StudentDocument).filter(StudentDocument.student_id == s.student_id).all()) for s in students]


@router.get("/students/{student_id}", response_model=StudentDetailResponse)
def get_student(student_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Get a single student's full profile including uploaded documents."""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    docs = db.query(StudentDocument).filter(StudentDocument.student_id == student_id).all()
    return _format_student(student, docs)


@router.patch("/students/{student_id}/decision", response_model=AccountDecisionResponse)
def decide_student_account(student_id: int, payload: AccountDecisionRequest, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Approve or reject a student account."""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if student.account_status != AccountStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Student is not pending approval (current: {student.account_status})")
    if payload.decision == "approve":
        student.account_status = AccountStatus.APPROVED
        message = "Student account approved"
    elif payload.decision == "reject":
        student.account_status = AccountStatus.REJECTED
        message = "Student account rejected"
    else:
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")
    db.commit()
    return {"message": message, "student_id": student_id, "new_status": student.account_status, "note": payload.note}


@router.patch("/students/{student_id}/edit", response_model=StudentDetailResponse)
def edit_student(student_id: int, payload: AdminEditStudentRequest, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Edit a student's profile info."""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if payload.name is not None: student.name = payload.name
    if payload.iban is not None: student.iban = payload.iban
    if payload.stpt_id is not None: student.stpt_id = payload.stpt_id
    db.commit()
    db.refresh(student)
    docs = db.query(StudentDocument).filter(StudentDocument.student_id == student_id).all()
    return _format_student(student, docs)


@router.get("/requests", response_model=list[ReimbursementRequestResponse])
def list_requests(status: Optional[str] = None, timeframe: Optional[str] = None, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """List all reimbursement requests with fraud detection results."""
    return RequestService.get_all_requests(db=db, status=status, timeframe=timeframe)


@router.patch("/requests/{request_id}/decision", response_model=ReimbursementRequestResponse)
def decide_request(request_id: int, payload: RequestDecisionRequest, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Approve, reject, or mark a request as under review."""
    result = RequestService.decide_request(db=db, request_id=request_id, decision=payload.decision, feedback=payload.note)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
