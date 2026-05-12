# app/schemas/student.py
from pydantic import BaseModel
from typing import Optional
from enum import Enum


class AccountStatus(str, Enum):
    INCOMPLETE = "incomplete"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class DocumentType(str, Enum):
    STUDENT_ID = "STUDENT_ID"
    STPT_CARD = "STPT_CARD"
    BANK_PROOF = "BANK_PROOF"


class DocumentsUploaded(BaseModel):
    student_id_photo: bool
    stpt_card: bool
    bank_proof: bool


class StudentProfileResponse(BaseModel):
    student_id: int
    name: Optional[str] = None
    email: str
    iban: Optional[str] = None
    stpt_id: Optional[str] = None
    account_status: AccountStatus
    documents_uploaded: DocumentsUploaded


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    iban: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    message: str
    document_type: str
    file_path: str
    ocr_status: Optional[str] = None
    extracted_stpt_id: Optional[str] = None
    note: Optional[str] = None


class StudentDocumentResponse(BaseModel):
    document_id: int
    document_type: DocumentType
    file_path: str
    uploaded_at: str


class StudentDetailResponse(BaseModel):
    student_id: int
    name: Optional[str] = None
    email: str
    iban: Optional[str] = None
    stpt_id: Optional[str] = None
    account_status: AccountStatus
    documents: list[StudentDocumentResponse] = []


class AdminEditStudentRequest(BaseModel):
    name: Optional[str] = None
    iban: Optional[str] = None
    stpt_id: Optional[str] = None


class AccountDecisionRequest(BaseModel):
    decision: str  # "approve" or "reject"
    note: Optional[str] = None


class AccountDecisionResponse(BaseModel):
    message: str
    student_id: int
    new_status: AccountStatus
    note: Optional[str] = None
