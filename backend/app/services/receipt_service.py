# app/services/receipt_service.py
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..database.models.receipt import Receipt
from ..database.models.receipt_ocr import ReceiptOCR
from ..database.models.request import Request as RequestModel, RequestStatus
from .fraud_detection_service import FraudDetectionService
from .validation.anomaly_service import AnomalyService
from .validation.exif_service import ExifService
from .validation.hash_service import HashService
from .validation.multi_ocr_service import MultiOCRService

#RESUBMIT_WINDOW_MINUTES = 30


class ReceiptService:
    """
    Orchestrates the full 5-layer fraud detection pipeline for a receipt upload.
    All business logic lives here — routers just call these methods.
    """

    @staticmethod
    def _save_file_permanently(temp_path: Path) -> tuple[str, Path, str]:
        """
        Move a receipt from the temp folder to its permanent location.
        Returns (receipt_uuid, permanent_path, relative_file_path)
        """
        year = datetime.now().year
        receipt_uuid = str(uuid.uuid4())
        permanent_dir = settings.RECEIPTS_DIR / str(year)
        permanent_dir.mkdir(parents=True, exist_ok=True)
        permanent_path = permanent_dir / f"{receipt_uuid}.jpg"
        shutil.copy(temp_path, permanent_path)
        relative_file_path = f"uploads/receipts/{year}/{receipt_uuid}.jpg"
        return receipt_uuid, permanent_path, relative_file_path

    @staticmethod
    def _create_request_and_receipt(
        db: Session,
        student_id: int,
        receipt_uuid: str,
        relative_file_path: str,
        sha256_hash: str,
        comment: Optional[str] = None
    ) -> tuple[RequestModel, Receipt]:
        """
        Create the Request and Receipt DB records after Layer 1 passes.
        Deletes any previous unconfirmed requests for this student first.
        Returns (request, receipt)
        """
        # Delete any previous unconfirmed requests for this student
        from sqlalchemy import false as sa_false
        old_unconfirmed = db.query(RequestModel).filter(
            RequestModel.student_id == student_id,
            RequestModel.confirmed.is_(False)
        ).all()
        for old_req in old_unconfirmed:
            for old_receipt in old_req.receipts:
                old_file = Path(old_receipt.file_path)
                if old_file.exists():
                    old_file.unlink()
            db.delete(old_req)
        if old_unconfirmed:
            db.flush()

        new_request = RequestModel(
            student_id=student_id,
            comment=comment or "Receipt submission",
            status=RequestStatus.PENDING,
            confirmed=False
        )
        db.add(new_request)
        db.flush()

        new_receipt = Receipt(
            receipt_id=receipt_uuid,
            student_id=student_id,
            request_id=new_request.request_id,
            file_path=relative_file_path,
            sha256_hash=sha256_hash
        )
        db.add(new_receipt)
        db.flush()

        return new_request, new_receipt

    @staticmethod
    def _attach_receipt_to_existing_request(
        db: Session,
        student_id: int,
        request_id: int,
        receipt_uuid: str,
        relative_file_path: str,
        sha256_hash: str,
    ) -> tuple[RequestModel, Receipt]:
        """
        Attach a new receipt to an existing request (used for resubmission).
        Returns (request, receipt)
        """
        request = db.query(RequestModel).filter(
            RequestModel.request_id == request_id
        ).first()

        new_receipt = Receipt(
            receipt_id=receipt_uuid,
            student_id=student_id,
            request_id=request_id,
            file_path=relative_file_path,
            sha256_hash=sha256_hash
        )
        db.add(new_receipt)
        db.flush()

        return request, new_receipt

    @staticmethod
    async def run_full_pipeline(
        db: Session,
        file_path: Path,
        student_id: int,
        filename: str,
        comment: Optional[str] = None,
        existing_request_id: Optional[int] = None
    ) -> Dict:
        """
        Run all 5 fraud detection layers on an uploaded receipt.

        If existing_request_id is provided, attaches the receipt to that request
        (resubmission flow). Otherwise creates a new request.

        Returns a structured result dict with layer results and final assessment.
        Early-exits with action='rejected' if Layer 1 or Layer 4 detect fraud.
        """

        # ── Layer 1: Hash & duplicate detection ──────────────────────────────
        layer1_result = await HashService.validate_file_integrity(
            db=db,
            file_path=file_path,
            student_id=student_id
        )

        if layer1_result["fraud_suspected"]:
            return {
                "action": "rejected",
                "message": "FRAUD ALERT: This receipt was already submitted by another student.",
                "layer1": layer1_result,
                "database_saved": False
            }

        if layer1_result["is_duplicate"]:
            return {
                "action": "rejected",
                "message": "DUPLICATE: You already submitted this exact receipt before.",
                "layer1": layer1_result,
                "database_saved": False
            }

        # ── Layer 1 passed — persist the file and create/attach DB records ───
        receipt_uuid, permanent_path, relative_file_path = ReceiptService._save_file_permanently(file_path)

        if existing_request_id:
            request, _ = ReceiptService._attach_receipt_to_existing_request(
                db=db,
                student_id=student_id,
                request_id=existing_request_id,
                receipt_uuid=receipt_uuid,
                relative_file_path=relative_file_path,
                sha256_hash=layer1_result["sha256_hash"]
            )
        else:
            request, _ = ReceiptService._create_request_and_receipt(
                db=db,
                student_id=student_id,
                receipt_uuid=receipt_uuid,
                relative_file_path=relative_file_path,
                sha256_hash=layer1_result["sha256_hash"],
                comment=comment
            )

        # ── Layer 2: EXIF metadata analysis ──────────────────────────────────
        layer2_result = ExifService.analyze_exif(permanent_path)
        FraudDetectionService.save_layer2_results(
            db=db,
            receipt_id=receipt_uuid,
            layer2_analysis=layer2_result
        )

        # ── Layer 3: OCR — extract & validate STPT ID ────────────────────────
        ocr_result = MultiOCRService.compare_all_ocr(permanent_path)
        consensus = ocr_result["consensus"]
        layer3_data = {
            "stpt_id": consensus["stpt_id"],
            "stpt_id_confidence": (
                0.95 if consensus["all_agree"] else
                0.85 if consensus["majority_agree"] else
                max(
                    ocr_result.get("easyocr", {}).get("stpt_id_confidence", 0),
                    ocr_result.get("google_cloud_vision", {}).get("stpt_id_confidence", 0)
                )
            ),
            "receipt_id": None,
            "receipt_id_confidence": 0.0,
            "average_confidence": 0.9 if consensus["all_agree"] else 0.7,
            "raw_text": ocr_result.get("google_cloud_vision", {}).get("raw_text", "")
        }
        FraudDetectionService.save_layer3_results(
            db=db,
            receipt_id=receipt_uuid,
            student_id=student_id,
            ocr_result=layer3_data,
            ocr_engine="consensus"
        )

        # ── Layer 4: Receipt ID anomaly detection ─────────────────────────────
        layer4_result = AnomalyService.analyze_receipt_id(
            db=db,
            receipt_id=receipt_uuid,
            easyocr_text=ocr_result["easyocr"]["raw_text"],
            google_vision_text=ocr_result["google_cloud_vision"]["raw_text"]
        )

        if layer4_result["success"]:
            FraudDetectionService.save_layer4_results(
                db=db,
                receipt_id=receipt_uuid,
                layer4_analysis=layer4_result
            )

        if layer4_result.get("is_duplicate"):
            db.commit()
            return {
                "action": "rejected",
                "message": f"DUPLICATE FRAUD: Receipt ID {layer4_result['extracted_receipt_id']} was already submitted.",
                "receipt_id": receipt_uuid,
                "request_id": request.request_id,
                "layer1": layer1_result,
                "layer2": layer2_result,
                "layer3": layer3_data,
                "layer4": layer4_result,
                "database_saved": True
            }

        # ── Layer 5: Final risk assessment ────────────────────────────────────
        risk_assessment = FraudDetectionService.update_final_risk_assessment(
            db=db,
            receipt_id=receipt_uuid,
            layer1_fraud=False,
            layer1_duplicate=False,
            layer4_risk=layer4_result.get("layer4_risk_score", 0.0)
        )

        db.commit()

        # ── Build response ────────────────────────────────────────────────────
        total_risk = risk_assessment.total_risk_score

        if total_risk >= 0.8:
            action = "flagged_high_risk"
            message = "HIGH RISK: Receipt saved but requires immediate admin review."
        elif total_risk >= 0.5:
            action = "flagged_medium_risk"
            message = "MEDIUM RISK: Receipt saved but flagged for admin review."
        else:
            action = "approved"
            message = "APPROVED: Receipt passed all validation checks."

        # OCR result for student feedback
        stpt_found = layer3_data["stpt_id"] is not None
        stpt_matches = risk_assessment.risk_factors["layer3_ocr"]["stpt_id_matches"]
        receipt_id_found = layer4_result.get("extracted_receipt_id") is not None

        return {
            "action": action,
            "message": message,
            "receipt_id": receipt_uuid,
            "request_id": request.request_id,
            "file_location": relative_file_path,
            "confirmed": request.confirmed,
            "layer1_hash": {
                "sha256_hash": layer1_result["sha256_hash"],
                "is_duplicate": False,
                "fraud_suspected": False
            },
            "layer2_exif": {
                "exif_status": layer2_result["exif_status"],
                "has_editing_software": layer2_result["has_editing_software"],
                "editing_software": layer2_result.get("editing_software"),
                "is_mobile_camera": layer2_result["is_mobile_camera"],
                "camera_model": layer2_result.get("camera_model"),
                "risk_score": layer2_result["risk_score"]
            },
            "layer3_ocr": {
                "extracted_stpt_id": layer3_data["stpt_id"],
                "stpt_id_found": stpt_found,
                "stpt_id_matches_student": stpt_matches,
                "ocr_consensus": consensus["all_agree"],
                "engines_agree_count": consensus["agreement_count"],
                "risk_score": risk_assessment.layer3_risk
            },
            "layer4_anomaly": {
                "extracted_receipt_id": layer4_result.get("extracted_receipt_id"),
                "receipt_id_found": receipt_id_found,
                "is_duplicate": layer4_result.get("is_duplicate", False),
                "similar_pattern_count": layer4_result.get("similar_pattern_count", 0),
                "assessment": layer4_result.get("assessment"),
                "risk_score": risk_assessment.layer4_risk
            },
            "final_assessment": {
                "total_risk_score": total_risk,
                "assessment": risk_assessment.assessment,
                "risk_breakdown": risk_assessment.risk_factors
            },
            "ocr_summary": {
                "stpt_id_found": stpt_found,
                "stpt_id_matches": stpt_matches,
                "receipt_id_found": receipt_id_found,
            },
            "database_saved": True
        }
