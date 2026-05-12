# app/schemas/request.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum
from .receipt import ReceiptResponse


class RequestStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class RequestDecisionRequest(BaseModel):
    decision: str  # "approve", "reject", "under_review"
    note: Optional[str] = None


class ReimbursementRequestResponse(BaseModel):
    request_id: int
    student_id: int
    status: RequestStatus
    comment: Optional[str] = None
    admin_feedback: Optional[str] = None
    submit_timestamp: datetime
    review_timestamp: Optional[datetime] = None
    receipts: list[ReceiptResponse] = []
