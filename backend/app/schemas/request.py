# app/schemas/request.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum
from .receipt import ReceiptResponse


class RequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RequestDecisionRequest(BaseModel):
    decision: str
    note: Optional[str] = None


class ReimbursementRequestResponse(BaseModel):
    request_id: int
    student_id: int
    status: RequestStatus
    comment: Optional[str] = None
    admin_feedback: Optional[str] = None
    submit_timestamp: datetime
    review_timestamp: Optional[datetime] = None
    confirmed: bool = False
    resubmission_count: int = 0
    last_resubmit_timestamp: Optional[datetime] = None
    receipts: list[ReceiptResponse] = []