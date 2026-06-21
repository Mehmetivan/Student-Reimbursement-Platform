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

def _sanitize_for_json(obj):
    """Convert PIL IFDRational and other non-serializable types to JSON-safe values."""
    if hasattr(obj, 'numerator') and hasattr(obj, 'denominator'):
        try:
            return float(obj)
        except Exception:
            return str(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='ignore')
    return obj

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
        result["raw_exif_data"] = _sanitize_for_json(raw_exif)

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


# ── Layer 3 (all engines compared — STPT ID only) ────────────────────────────

@router.post("/compare-ocr")
async def test_compare_ocr(file: UploadFile = File(...)):
    """Compare Tesseract, EasyOCR, and Google Cloud Vision for STPT customer ID extraction."""
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


# ── Layer 3 + 4 (both IDs extracted and compared) ────────────────────────────

@router.post("/ocr-extraction")
async def test_ocr_extraction(file: UploadFile = File(...)):
    """
    Extract and compare both IDs from the receipt using all available OCR engines.

    - STPT Customer ID (SERIE CARD: 555845) — used in Layer 3 to verify the card belongs to the student
    - Receipt Transaction ID (324-19204-555845) — used in Layer 4 to verify the transaction is genuine

    Shows per-engine results and consensus for both IDs side by side.
    """
    validate_upload_file(file)
    temp_path = _save_temp(file)

    try:
        # Run all 3 engines
        tesseract_result = MultiOCRService.extract_text_tesseract(temp_path)
        easyocr_result = MultiOCRService.extract_text_easyocr(temp_path)
        google_result = MultiOCRService.extract_text_google_vision(temp_path)

        # Extract STPT customer ID from each engine (Layer 3)
        tesseract_stpt, tesseract_stpt_conf = MultiOCRService.extract_stpt_id(tesseract_result["raw_text"])
        easyocr_stpt, easyocr_stpt_conf = MultiOCRService.extract_stpt_id(easyocr_result["raw_text"])
        google_stpt, google_stpt_conf = MultiOCRService.extract_stpt_id(google_result["raw_text"])

        # Extract receipt transaction ID from EasyOCR and Google Vision (Layer 4)
        # Tesseract is not used for receipt ID extraction — only EasyOCR and Google Vision
        easyocr_receipt_id, easyocr_receipt_conf = AnomalyService.extract_receipt_id_from_ocr(
            easyocr_result["raw_text"], ""
        )
        google_receipt_id, google_receipt_conf = AnomalyService.extract_receipt_id_from_ocr(
            "", google_result["raw_text"]
        )
        # Consensus for receipt ID (EasyOCR + Google Vision only)
        receipt_id_consensus, receipt_id_conf = AnomalyService.extract_receipt_id_from_ocr(
            easyocr_result["raw_text"],
            google_result["raw_text"]
        )

        # STPT ID consensus (all 3 engines — same logic as compare-ocr)
        all_agree = False
        majority_agree = False
        stpt_consensus = None
        agreement_count = 0

        if tesseract_stpt and tesseract_stpt == easyocr_stpt == google_stpt:
            stpt_consensus = tesseract_stpt
            all_agree = True
            majority_agree = True
            agreement_count = 3
        elif tesseract_stpt and tesseract_stpt == easyocr_stpt:
            stpt_consensus = tesseract_stpt
            majority_agree = True
            agreement_count = 2
        elif tesseract_stpt and tesseract_stpt == google_stpt:
            stpt_consensus = tesseract_stpt
            majority_agree = True
            agreement_count = 2
        elif easyocr_stpt and easyocr_stpt == google_stpt:
            stpt_consensus = easyocr_stpt
            majority_agree = True
            agreement_count = 2
        else:
            best = max(
                [("Tesseract", tesseract_stpt, tesseract_stpt_conf),
                 ("EasyOCR", easyocr_stpt, easyocr_stpt_conf),
                 ("Google Vision", google_stpt, google_stpt_conf)],
                key=lambda x: x[2]
            )
            stpt_consensus = best[1]
            agreement_count = 1

        return {
            "file_info": {
                "filename": file.filename,
                "file_size": temp_path.stat().st_size
            },

            # Per-engine results
            "tesseract": {
                "ocr_engine": "Tesseract",
                "success": tesseract_result["success"],
                "raw_text": tesseract_result["raw_text"],
                "processing_time_seconds": tesseract_result["processing_time_seconds"],
                "error": tesseract_result["error"],
                # STPT customer ID
                "stpt_customer_id_found": tesseract_stpt,
                "stpt_customer_id_confidence": tesseract_stpt_conf,
                # Receipt transaction ID — Tesseract not used for this
                "receipt_transaction_id_found": None,
                "receipt_transaction_id_confidence": 0.0,
                "note": "Tesseract not used for receipt transaction ID extraction"
            },

            "easyocr": {
                "ocr_engine": "EasyOCR",
                "success": easyocr_result["success"],
                "raw_text": easyocr_result["raw_text"],
                "processing_time_seconds": easyocr_result["processing_time_seconds"],
                "average_confidence": easyocr_result.get("average_confidence"),
                "detected_segments": easyocr_result.get("detected_segments"),
                "error": easyocr_result["error"],
                # STPT customer ID
                "stpt_customer_id_found": easyocr_stpt,
                "stpt_customer_id_confidence": easyocr_stpt_conf,
                # Receipt transaction ID
                "receipt_transaction_id_found": easyocr_receipt_id,
                "receipt_transaction_id_confidence": easyocr_receipt_conf
            },

            "google_cloud_vision": {
                "ocr_engine": "Google Cloud Vision",
                "success": google_result["success"],
                "raw_text": google_result["raw_text"],
                "processing_time_seconds": google_result["processing_time_seconds"],
                "detected_segments": google_result.get("detected_segments"),
                "error": google_result["error"],
                # STPT customer ID
                "stpt_customer_id_found": google_stpt,
                "stpt_customer_id_confidence": google_stpt_conf,
                # Receipt transaction ID
                "receipt_transaction_id_found": google_receipt_id,
                "receipt_transaction_id_confidence": google_receipt_conf
            },

            # Consensus results
            "consensus": {
                # STPT customer ID consensus (all 3 engines)
                "stpt_customer_id": stpt_consensus,
                "stpt_agreement_count": agreement_count,
                "stpt_total_engines": 3,
                "stpt_all_agree": all_agree,
                "stpt_majority_agree": majority_agree,

                # Receipt transaction ID consensus (EasyOCR + Google Vision only)
                "receipt_transaction_id": receipt_id_consensus,
                "receipt_id_confidence": receipt_id_conf,
                "receipt_id_engines_used": 2,
                "receipt_id_engines_agree": easyocr_receipt_id == google_receipt_id and easyocr_receipt_id is not None
            },

            # Performance
            "performance_comparison": {
                "fastest_engine": min(
                    [tesseract_result, easyocr_result, google_result],
                    key=lambda x: x["processing_time_seconds"] if x["success"] else float('inf')
                )["ocr_engine"],
                "total_processing_time": round(
                    tesseract_result["processing_time_seconds"] +
                    easyocr_result["processing_time_seconds"] +
                    google_result["processing_time_seconds"], 2
                ),
                "success_rate": sum([
                    tesseract_result["success"],
                    easyocr_result["success"],
                    google_result["success"]
                ]) / 3
            },

            # Summary for thesis
            "thesis_analysis": {
                "engines_found_stpt_id": sum([
                    tesseract_stpt is not None,
                    easyocr_stpt is not None,
                    google_stpt is not None
                ]),
                "engines_found_receipt_id": sum([
                    easyocr_receipt_id is not None,
                    google_receipt_id is not None
                ]),
                "both_ids_extracted": stpt_consensus is not None and receipt_id_consensus is not None,
                "extraction_complete": stpt_consensus is not None and receipt_id_consensus is not None
            }
        }

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
# This file already exists from earlier build
