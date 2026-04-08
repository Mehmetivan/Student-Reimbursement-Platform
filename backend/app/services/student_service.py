# app/services/student_service.py
import shutil
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..database.models.student import Student, AccountStatus
from ..database.models.student_document import StudentDocument, DocumentType
from .validation.multi_ocr_service import MultiOCRService


class StudentService:

    # ── Profile ───────────────────────────────────────────────────────────────

    @staticmethod
    def get_profile(db: Session, student: Student) -> dict:
        docs = db.query(StudentDocument).filter(
            StudentDocument.student_id == student.student_id
        ).all()
        uploaded_types = {d.document_type for d in docs}

        return {
            "student_id": student.student_id,
            "name": student.name,
            "email": student.email,
            "iban": student.iban,
            "stpt_id": student.stpt_id,
            "account_status": student.account_status,
            "documents_uploaded": {
                "student_id_photo": DocumentType.STUDENT_ID in uploaded_types,
                "stpt_card": DocumentType.STPT_CARD in uploaded_types,
                "bank_proof": DocumentType.BANK_PROOF in uploaded_types,
            }
        }

    @staticmethod
    def update_profile(
        db: Session,
        student: Student,
        name: Optional[str] = None,
        iban: Optional[str] = None
    ) -> dict:
        """
        Update student profile fields (name and IBAN).
        stpt_id is set automatically when the STPT card is uploaded, not here.
        """
        if name is not None:
            student.name = name
        if iban is not None:
            student.iban = iban

        # Check if profile is now complete enough to move to pending_approval
        StudentService._check_and_advance_status(db, student)

        db.commit()
        db.refresh(student)
        return StudentService.get_profile(db, student)

    @staticmethod
    def _check_and_advance_status(db: Session, student: Student):
        """
        If all 3 documents are uploaded and name + IBAN are filled in,
        automatically advance status to pending_approval.
        Only advances from INCOMPLETE — doesn't override admin decisions.
        """
        if student.account_status != AccountStatus.INCOMPLETE:
            return

        docs = db.query(StudentDocument).filter(
            StudentDocument.student_id == student.student_id
        ).all()
        uploaded_types = {d.document_type for d in docs}

        has_all_docs = (
            DocumentType.STUDENT_ID in uploaded_types and
            DocumentType.STPT_CARD in uploaded_types and
            DocumentType.BANK_PROOF in uploaded_types
        )
        has_profile = bool(student.name and student.iban and student.stpt_id)

        if has_all_docs and has_profile:
            student.account_status = AccountStatus.PENDING_APPROVAL

    # ── Document upload ───────────────────────────────────────────────────────

    @staticmethod
    def _save_document_file(file_path: Path, student_id: int, doc_type: DocumentType) -> str:
        """Save document file to permanent location, return relative path."""
        ext = file_path.suffix.lower()
        doc_uuid = str(uuid.uuid4())
        dest_dir = settings.DOCUMENTS_DIR / str(student_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{doc_type.value}_{doc_uuid}{ext}"
        shutil.copy(file_path, dest_path)
        return str(dest_path)

    @staticmethod
    def _upsert_document(
        db: Session,
        student_id: int,
        doc_type: DocumentType,
        file_path: str
    ) -> StudentDocument:
        """
        Insert or replace a document record.
        If student already has this document type, replace the file path.
        """
        existing = db.query(StudentDocument).filter(
            StudentDocument.student_id == student_id,
            StudentDocument.document_type == doc_type
        ).first()

        if existing:
            existing.file_path = file_path
            db.commit()
            db.refresh(existing)
            return existing

        doc = StudentDocument(
            student_id=student_id,
            document_type=doc_type,
            file_path=file_path
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def upload_student_id(
        db: Session,
        student: Student,
        temp_path: Path
    ) -> dict:
        """
        Store the student ID photo. No OCR — staff reviews manually.
        """
        file_path = StudentService._save_document_file(
            temp_path, student.student_id, DocumentType.STUDENT_ID
        )
        StudentService._upsert_document(
            db, student.student_id, DocumentType.STUDENT_ID, file_path
        )
        StudentService._check_and_advance_status(db, student)
        db.commit()

        return {
            "message": "Student ID photo uploaded successfully",
            "document_type": "STUDENT_ID",
            "file_path": file_path
        }

    @staticmethod
    def upload_stpt_card(
        db: Session,
        student: Student,
        temp_path: Path
    ) -> dict:
        """
        Store the STPT card photo and immediately run OCR to extract
        the STPT customer ID. Stores the extracted ID on the student record.
        This ID is later used in Layer 3 to validate receipts.
        """
        file_path = StudentService._save_document_file(
            temp_path, student.student_id, DocumentType.STPT_CARD
        )
        StudentService._upsert_document(
            db, student.student_id, DocumentType.STPT_CARD, file_path
        )

        # Run OCR on the card to extract STPT customer ID
        # Uses dedicated card extraction (not the receipt pipeline)
        ocr_result = MultiOCRService.extract_card_id(Path(file_path))
        extracted_stpt_id = ocr_result.get("extracted_stpt_id")

        ocr_status = "not_found"
        if extracted_stpt_id:
            student.stpt_id = extracted_stpt_id
            ocr_status = "extracted"

        StudentService._check_and_advance_status(db, student)
        db.commit()

        return {
            "message": "STPT card uploaded successfully",
            "document_type": "STPT_CARD",
            "file_path": file_path,
            "ocr_status": ocr_status,
            "extracted_stpt_id": extracted_stpt_id,
            "note": (
                "STPT ID extracted and saved to your profile."
                if extracted_stpt_id
                else "Could not extract STPT ID automatically. An admin may update it manually."
            )
        }

    @staticmethod
    def upload_bank_proof(
        db: Session,
        student: Student,
        temp_path: Path
    ) -> dict:
        """
        Store the bank statement document. IBAN is entered manually by the student,
        this document is just stored as proof for staff to verify.
        """
        file_path = StudentService._save_document_file(
            temp_path, student.student_id, DocumentType.BANK_PROOF
        )
        StudentService._upsert_document(
            db, student.student_id, DocumentType.BANK_PROOF, file_path
        )
        StudentService._check_and_advance_status(db, student)
        db.commit()

        return {
            "message": "Bank proof document uploaded successfully",
            "document_type": "BANK_PROOF",
            "file_path": file_path
        }
