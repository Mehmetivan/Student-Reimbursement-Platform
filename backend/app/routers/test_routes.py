# app/routers/test_routes.py
# Development-only endpoints for testing individual fraud detection layers.
# Remove in Phase 6 before production.
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models.receipt import Receipt
from ..database.models.receipt_ocr import ReceiptOCR
from ..database.models.request import Request as RequestModel, RequestStatus
from ..database.session import SessionLocal
from ..services.fraud_detection_service import FraudDetectionService
from ..services.receipt_service import ReceiptService
from ..services.validation.anomaly_service import AnomalyService
from ..services.validation.exif_service import ExifService
from ..services.validation.hash_service import HashService
from ..services.validation.multi_ocr_service import MultiOCRService
from ..services.validation.ocr_service import OCRService

router = APIRouter(prefix="/test", tags=["test — dev only"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def validate_upload_file(file: UploadFile) -> None:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(settings.ALLOWED_IMAGE_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"File type '{suffix}' not allowed. Accepted: {allowed}"
        )


def _save_temp(file: UploadFile) -> Path:
    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return temp_path


# ── Layer 1 ───────────────────────────────────────────────────────────────────

@router.post("/hash-layer")
async def test_hash_layer(
    file: UploadFile = File(...),
    student_id: int = 1,
    db: Session = Depends(get_db)
):
    """Test Layer 1: SHA-256 hash & duplicate detection."""
    validate_upload_file(file)
    temp_path = _save_temp(file)

    try:
        result = await HashService.validate_file_integrity(
            db=db, file_path=temp_path, student_id=student_id
        )
        result["filename"] = file.filename
        result["file_size"] = temp_path.stat().st_size
        result["student_id"] = student_id

        if result["fraud_suspected"]:
            result["message"] = "FRAUD ALERT: Receipt already submitted by another student."
            result["action"] = "rejected"
        elif result["is_duplicate"]:
            result["message"] = "DUPLICATE: You already submitted this receipt."
            result["action"] = "rejected"
        else:
            year = __import__('datetime').datetime.now().year
            receipt_uuid = str(uuid.uuid4())
            permanent_dir = settings.RECEIPTS_DIR / str(year)
            permanent_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(temp_path, permanent_dir / f"{receipt_uuid}.jpg")

            new_request = RequestModel(
                student_id=student_id,
                comment="Test — hash layer",
                status=RequestStatus.PENDING
            )
            db.add(new_request)
            db.flush()

            new_receipt = Receipt(
                receipt_id=receipt_uuid,
                student_id=student_id,
                request_id=new_request.request_id,
                file_path=f"uploads/receipts/{year}/{receipt_uuid}.jpg",
                sha256_hash=result["sha256_hash"]
            )
            db.add(new_receipt)
            db.commit()

            result["message"] = "File passed Layer 1 and saved."
            result["action"] = "saved"
            result["receipt_id"] = receipt_uuid

        return result
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ── Layer 2 ───────────────────────────────────────────────────────────────────

@router.post("/exif-layer")
async def test_exif_layer(file: UploadFile = File(...)):
    """Test Layer 2: EXIF metadata analysis."""
    validate_upload_file(file)
    temp_path = _save_temp(file)

    try:
        raw_exif = ExifService.extract_exif(temp_path)
        result = ExifService.analyze_exif(temp_path)
        result["filename"] = file.filename
        result["file_size"] = temp_path.stat().st_size
        result["raw_exif_data"] = raw_exif

        if result["assessment"] == "high_risk":
            result["message"] = "HIGH RISK: Image shows signs of editing or manipulation."
        elif result["assessment"] == "medium_risk":
            result["message"] = "MEDIUM RISK: Some suspicious indicators detected."
        else:
            result["message"] = "LOW RISK: Image appears legitimate."

        return result
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ── Layer 3 (single engine) ───────────────────────────────────────────────────

@router.post("/ocr-layer")
async def test_ocr_layer(file: UploadFile = File(...)):
    """Test Layer 3: OCR text extraction (Tesseract only)."""
    validate_upload_file(file)
    temp_path = _save_temp(file)

    try:
        result = OCRService.analyze_receipt_text(temp_path)
        result["filename"] = file.filename
        result["file_size"] = temp_path.stat().st_size

        if result["stpt_id"]:
            result["message"] = f"STPT ID found: {result['stpt_id']} (confidence: {result['stpt_id_confidence']:.2f})"
        else:
            result["message"] = "STPT ID not found in receipt text."

        if result["raw_text"]:
            result["text_preview"] = result["raw_text"][:500]

        return result
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ── Layer 3 (all engines compared) ───────────────────────────────────────────

@router.post("/compare-ocr")
async def test_compare_ocr(file: UploadFile = File(...)):
    """Compare Tesseract, EasyOCR, and Google Cloud Vision side by side."""
    validate_upload_file(file)
    temp_path = _save_temp(file)

    try:
        comparison = MultiOCRService.compare_all_ocr(temp_path)
        comparison["file_info"] = {
            "filename": file.filename,
            "file_size": temp_path.stat().st_size
        }

        consensus = comparison["consensus"]
        if consensus["stpt_id"]:
            if consensus["all_agree"]:
                comparison["message"] = f"ALL ENGINES AGREE: STPT ID = {consensus['stpt_id']}"
            elif consensus["majority_agree"]:
                comparison["message"] = f"MAJORITY CONSENSUS: STPT ID = {consensus['stpt_id']} ({consensus['agreement_count']}/3 engines)"
            else:
                comparison["message"] = f"SINGLE DETECTION: STPT ID = {consensus['stpt_id']} (1 engine only)"
        else:
            comparison["message"] = "No STPT ID found by any engine."

        return comparison
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ── Layer 4 ───────────────────────────────────────────────────────────────────

@router.post("/anomaly-layer")
async def test_anomaly_layer(
    file: UploadFile = File(...),
    student_id: int = 1,
    db: Session = Depends(get_db)
):
    """Test Layer 4: Receipt ID structural anomaly detection."""
    validate_upload_file(file)
    temp_path = _save_temp(file)

    try:
        ocr_comparison = MultiOCRService.compare_all_ocr(temp_path)
        easyocr_text = ocr_comparison["easyocr"]["raw_text"]
        google_text = ocr_comparison["google_cloud_vision"]["raw_text"]

        receipt_uuid = str(uuid.uuid4())

        test_request = RequestModel(
            student_id=student_id,
            comment="Test — anomaly layer",
            status=RequestStatus.PENDING
        )
        db.add(test_request)
        db.flush()

        test_receipt = Receipt(
            receipt_id=receipt_uuid,
            student_id=student_id,
            request_id=test_request.request_id,
            file_path=f"test/{receipt_uuid}.jpg",
            sha256_hash="test_hash_layer4"
        )
        db.add(test_receipt)
        db.flush()

        extracted_id, ocr_conf = AnomalyService.extract_receipt_id_from_ocr(easyocr_text, google_text)
        similar_patterns_found = []

        if extracted_id:
            structure_analysis = AnomalyService.analyze_structure(extracted_id)

            mock_ocr = ReceiptOCR(
                receipt_id=receipt_uuid,
                ocr_engine_used="consensus",
                extracted_receipt_id=extracted_id,
                raw_ocr_text=google_text[:500]
            )
            db.add(mock_ocr)
            db.flush()

            if structure_analysis["valid_format"]:
                similar_patterns_found = AnomalyService.find_similar_patterns(
                    db, structure_analysis, exclude_receipt_id=receipt_uuid
                )

        layer4_result = AnomalyService.analyze_receipt_id(
            db=db,
            receipt_id=receipt_uuid,
            easyocr_text=easyocr_text,
            google_vision_text=google_text
        )
        db.commit()

        assessment = layer4_result.get("assessment", "unknown")
        risk = layer4_result.get("layer4_risk_score", 0)

        return {
            "action": "rejected_duplicate" if layer4_result.get("is_duplicate") else assessment,
            "receipt_id": receipt_uuid,
            "filename": file.filename,
            "layer4_analysis": {
                "extracted_receipt_id": layer4_result.get("extracted_receipt_id"),
                "ocr_confidence": layer4_result.get("ocr_confidence"),
                "structure_pattern": layer4_result.get("structure"),
                "is_duplicate": layer4_result.get("is_duplicate", False),
                "similar_receipts_found": layer4_result.get("similar_pattern_count", 0),
                "assessment": assessment,
                "risk_score": risk
            },
            "explanation": {
                "what_happened": AnomalyService._get_explanation(layer4_result),
                "why_this_risk": AnomalyService._get_risk_explanation(assessment, risk),
                "next_steps": AnomalyService._get_next_steps(assessment)
            }
        }
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ── All layers combined ───────────────────────────────────────────────────────

@router.post("/combined-layers")
async def test_combined_layers(
    file: UploadFile = File(...),
    student_id: int = 1,
    db: Session = Depends(get_db)
):
    """
    Run all 5 layers end-to-end. Delegates to ReceiptService
    so /test/combined-layers and /receipts/submit share identical logic.
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
            student_id=student_id,
            filename=file.filename
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
