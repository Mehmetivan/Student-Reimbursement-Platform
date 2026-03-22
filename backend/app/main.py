# app/main.py

# app/main.py
import multiprocessing
multiprocessing.set_start_method('spawn', force=True)

# Then your regular imports...
from fastapi import FastAPI
# etc...

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database.base import Base
from .database.session import engine
from .config import settings

# Import all models to ensure they're registered with Base
from .database.models.student import Student
from .database.models.user import User
from .database.models.request import Request
from .database.models.receipt import Receipt
from .database.models.student_document import StudentDocument
from .services.validation.exif_service import ExifService
from .services.validation.ocr_service import OCRService
from .services.validation.multi_ocr_service import MultiOCRService

from .database.models.receipt_metadata import ReceiptMetadata
from .database.models.receipt_ocr import ReceiptOCR
from .database.models.receipt_anomalies import ReceiptAnomalies
from .database.models.receipt_risk_assessment import ReceiptRiskAssessment
from .services.fraud_detection_service import FraudDetectionService
#from .services.validation.anomaly_service import AnomalyService
from .services.validation.anomaly_service import AnomalyService

from fastapi import UploadFile, File, Depends
from sqlalchemy.orm import Session
from .database.session import SessionLocal
from .services.validation.hash_service import HashService
from pathlib import Path
import shutil

app = FastAPI(
    title="Student Reimbursement Platform",
    description="Multi-layer fraud detection system for public transport reimbursements",
    version="1.0.0"
)

# CORS middleware for frontend communication. (betnween client req and api logic)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all database tables
Base.metadata.create_all(bind=engine)





def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Test endpoint for Layer 1
@app.post("/test/hash-layer")
async def test_hash_layer(
    file: UploadFile = File(...),
    student_id: int = 1,
    db: Session = Depends(get_db)
):
    """
    Test Layer 1: File Integrity & Duplicate Detection
    
    Upload a file to test:
    - SHA-256 hash computation
    - Duplicate detection within student submissions
    - Global duplicate detection (fraud)
    - Save to database if no duplicates found
    """
    
    #additional layers will be added as the project progesses. Only layer 1&2 at the moment


    # Save uploaded file temporarily
    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save file
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Run Layer 1 validation
        result = await HashService.validate_file_integrity(
            db=db,
            file_path=temp_path,
            student_id=student_id
        )
        
        # Add file info to result
        result["filename"] = file.filename
        result["file_size"] = temp_path.stat().st_size
        result["student_id"] = student_id
        
        # Interpretation and action
        if result["fraud_suspected"]:
            result["message"] = "⚠️ FRAUD ALERT: This receipt was already submitted by another student!"
            result["action"] = "rejected"
        elif result["is_duplicate"]:
            result["message"] = "⚠️ You already submitted this exact receipt before."
            result["action"] = "rejected"
        else:
            # Save to database
            from datetime import datetime
            import uuid
            
            # Create permanent file path
            year = datetime.now().year
            receipt_uuid = str(uuid.uuid4())
            permanent_dir = settings.RECEIPTS_DIR / str(year)
            permanent_dir.mkdir(parents=True, exist_ok=True)
            permanent_path = permanent_dir / f"{receipt_uuid}.jpg"
            
            # Move file to permanent location
            shutil.copy(temp_path, permanent_path)
            
            # Create a dummy request first (normally this would come from the user)
            from .database.models.request import Request as RequestModel, RequestStatus
            new_request = RequestModel(
                student_id=student_id,
                comment="Test upload via hash layer",
                status=RequestStatus.PENDING
            )
            db.add(new_request)
            db.flush()  # Get the request_id
            
            # Store relative path (from uploads directory)
            relative_file_path = f"uploads/receipts/{year}/{receipt_uuid}.jpg"
            
            # Save receipt to database
            new_receipt = Receipt(
                receipt_id=receipt_uuid,
                student_id=student_id,
                request_id=new_request.request_id,
                file_path=relative_file_path,
                sha256_hash=result["sha256_hash"]
            )
            db.add(new_receipt)
            db.commit()
            
            result["message"] = "✅ File passed Layer 1 validation and saved to database!"
            result["action"] = "saved"
            result["receipt_id"] = receipt_uuid
            result["file_location"] = relative_file_path
        
        return result
        
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


# LAYER 2 - EXIF METADATA ANALYSIS

from .services.validation.exif_service import ExifService

@app.post("/test/exif-layer")
async def test_exif_layer(file: UploadFile = File(...)):
    """
    Test Layer 2: EXIF Metadata Analysis
    
    Upload an image to test:
    - EXIF data extraction
    - Editing software detection
    - Mobile camera verification
    - Photo age calculation
    - Risk scoring
    """
    
    # Save uploaded file temporarily
    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save file
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract raw EXIF data first
        raw_exif = ExifService.extract_exif(temp_path)
        
        # Run Layer 2 analysis
        result = ExifService.analyze_exif(temp_path)
        
        # Add file info
        result["filename"] = file.filename
        result["file_size"] = temp_path.stat().st_size
        
        # Add raw EXIF data for testing
        result["raw_exif_data"] = raw_exif
        
        # Add interpretation
        if result["assessment"] == "high_risk":
            result["message"] = "🚨 HIGH RISK: Image shows signs of editing or manipulation"
        elif result["assessment"] == "medium_risk":
            result["message"] = "⚠️ MEDIUM RISK: Some suspicious indicators detected"
        else:
            result["message"] = "✅ LOW RISK: Image appears legitimate"
        
        # Add detailed explanation
        explanations = []
        if result["has_editing_software"]:
            explanations.append(f"Editing software detected: {result['editing_software']}")
        if not result["exif_exists"]:
            explanations.append("No EXIF data (possibly screenshot or heavily processed)")
        if result["is_mobile_camera"]:
            explanations.append(f"Photo taken with mobile device: {result['camera_model']}")
        if result["photo_age_days"] and result["photo_age_days"] > 90:
            explanations.append(f"Photo is {result['photo_age_days']} days old")
        
        result["explanation"] = explanations
        
        return result
        
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


# Replace your /test/combined-layers endpoint in main.py with this:

@app.post("/test/combined-layers")
async def test_combined_layers(
    file: UploadFile = File(...),
    student_id: int = 1,
    db: Session = Depends(get_db)
):
    """
    Test Complete Receipt Upload with Layers 1, 2, and 3
    
    - Layer 1: Hash & duplicate detection
    - Layer 2: EXIF analysis
    - Layer 3: OCR & STPT ID validation
    - Saves all results to database
    """
    
    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save file
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # ===== LAYER 1: Hash Validation =====
        layer1_result = await HashService.validate_file_integrity(
            db=db,
            file_path=temp_path,
            student_id=student_id
        )
        
        # Check if rejected by Layer 1
        if layer1_result["fraud_suspected"]:
            return {
                "action": "rejected",
                "message": "🚫 FRAUD ALERT: This receipt was already submitted by another student!",
                "layer1": layer1_result,
                "database_saved": False
            }
        
        if layer1_result["is_duplicate"]:
            return {
                "action": "rejected",
                "message": "🚫 DUPLICATE: You already submitted this exact receipt before.",
                "layer1": layer1_result,
                "database_saved": False
            }
        
        # ===== Layer 1 PASSED - Save Receipt =====
        from datetime import datetime
        import uuid
        
        year = datetime.now().year
        receipt_uuid = str(uuid.uuid4())
        permanent_dir = settings.RECEIPTS_DIR / str(year)
        permanent_dir.mkdir(parents=True, exist_ok=True)
        permanent_path = permanent_dir / f"{receipt_uuid}.jpg"
        
        shutil.copy(temp_path, permanent_path)
        
        # Create request
        from .database.models.request import Request as RequestModel, RequestStatus
        new_request = RequestModel(
            student_id=student_id,
            comment="Test upload via combined layers",
            status=RequestStatus.PENDING
        )
        db.add(new_request)
        db.flush()
        
        # Save receipt
        relative_file_path = f"uploads/receipts/{year}/{receipt_uuid}.jpg"
        new_receipt = Receipt(
            receipt_id=receipt_uuid,
            student_id=student_id,
            request_id=new_request.request_id,
            file_path=relative_file_path,
            sha256_hash=layer1_result["sha256_hash"]
        )
        db.add(new_receipt)
        db.flush()
        
        # ===== LAYER 2: EXIF Analysis =====
        layer2_result = ExifService.analyze_exif(permanent_path)
        
        from .services.fraud_detection_service import FraudDetectionService
        
        FraudDetectionService.save_layer2_results(
            db=db,
            receipt_id=receipt_uuid,
            layer2_analysis=layer2_result
        )
        
        # ===== LAYER 3: OCR Analysis =====
        # Use the best OCR engine (Google Vision if available, otherwise EasyOCR)
        ocr_result = MultiOCRService.compare_all_ocr(permanent_path)
        
        # Use consensus result (if multiple engines agree)
        consensus = ocr_result["consensus"]
        layer3_data = {
            "stpt_id": consensus["stpt_id"],
            "stpt_id_confidence": 0.9 if consensus["majority_agree"] else 0.5,
            "receipt_id": None,  # Can extract from individual engines if needed
            "receipt_id_confidence": 0.0,
            "average_confidence": 0.9 if consensus["all_agree"] else 0.7,
            "raw_text": ocr_result.get("google_cloud_vision", {}).get("raw_text", "")
        }
        
        # Save Layer 3 OCR results and validate STPT ID
        FraudDetectionService.save_layer3_results(
            db=db,
            receipt_id=receipt_uuid,
            student_id=student_id,
            ocr_result=layer3_data,
            ocr_engine="consensus"
        )
        
        # ===== LAYER 5: Final Risk Assessment =====
        risk_assessment = FraudDetectionService.update_final_risk_assessment(
            db=db,
            receipt_id=receipt_uuid,
            layer1_fraud=False,
            layer1_duplicate=False
        )
        
        db.commit()
        
        # ===== Build Response =====
        total_risk = risk_assessment.total_risk_score
        
        if total_risk >= 0.8:
            action = "flagged_high_risk"
            message = "🚨 HIGH RISK: Receipt saved but requires immediate admin review"
        elif total_risk >= 0.5:
            action = "flagged_medium_risk"
            message = "⚠️ MEDIUM RISK: Receipt saved but flagged for admin review"
        else:
            action = "approved"
            message = "✅ APPROVED: Receipt passed all validation checks"
        
        return {
            "action": action,
            "message": message,
            "receipt_id": receipt_uuid,
            "file_location": relative_file_path,
            
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
                "stpt_id_matches_student": risk_assessment.risk_factors["layer3_ocr"]["stpt_id_matches"],
                "ocr_consensus": consensus["all_agree"],
                "engines_agree_count": consensus["agreement_count"],
                "risk_score": risk_assessment.layer3_risk
            },
            
            "final_assessment": {
                "total_risk_score": total_risk,
                "assessment": risk_assessment.assessment,
                "risk_breakdown": risk_assessment.risk_factors
            },
            
            "database_saved": True
        }
        
    finally:
        if temp_path.exists():
            temp_path.unlink()

@app.post("/test/ocr-layer")
async def test_ocr_layer(file: UploadFile = File(...)):
    """
    Test Layer 3: OCR Text Extraction
    
    Upload a receipt image to test:
    - Text extraction via Tesseract OCR
    - STPT ID extraction (SERIE CARD:555845)
    - Receipt ID extraction
    - Confidence scoring
    """
    
    # Save uploaded file temporarily
    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save file
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Run OCR analysis
        result = OCRService.analyze_receipt_text(temp_path)
        
        # Add file info
        result["filename"] = file.filename
        result["file_size"] = temp_path.stat().st_size
        
        # Add interpretation
        if result["stpt_id"]:
            result["message"] = f"✅ STPT ID FOUND: {result['stpt_id']} (confidence: {result['stpt_id_confidence']:.2f})"
        else:
            result["message"] = "⚠️ STPT ID NOT FOUND in receipt text"
        
        # Show what OCR saw (first 500 chars for readability)
        if result["raw_text"]:
            result["text_preview"] = result["raw_text"][:500] + "..." if len(result["raw_text"]) > 500 else result["raw_text"]
        
        return result
        
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink() 

@app.post("/test/compare-ocr")
async def test_compare_ocr(file: UploadFile = File(...)):
    """
    Compare all three OCR engines: Tesseract, EasyOCR, Google Cloud Vision
    
    Perfect for thesis research - shows:
    - Which OCR is most accurate
    - Which is fastest
    - Consensus results
    - Detailed comparison metrics
    
    Upload a receipt and see all three OCRs side-by-side!
    """
    
    # Save uploaded file temporarily
    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save file
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Run all three OCR engines and compare
        comparison = MultiOCRService.compare_all_ocr(temp_path)
        
        # Add file metadata
        comparison["file_info"] = {
            "filename": file.filename,
            "file_size": temp_path.stat().st_size
        }
        
        # Add interpretation message
        consensus = comparison["consensus"]
        if consensus["stpt_id"]:
            if consensus["all_agree"]:
                comparison["message"] = f"✅ ALL ENGINES AGREE: STPT ID = {consensus['stpt_id']}"
            elif consensus["majority_agree"]:
                comparison["message"] = f"⚠️ MAJORITY CONSENSUS: STPT ID = {consensus['stpt_id']} ({consensus['agreement_count']}/3 engines)"
            else:
                comparison["message"] = f"❓ SINGLE DETECTION: STPT ID = {consensus['stpt_id']} (only 1 engine found it)"
        else:
            comparison["message"] = "❌ NO STPT ID FOUND by any engine"
        
        return comparison
        
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()                       


@app.post("/test/anomaly-layer")
async def test_anomaly_layer(
    file: UploadFile = File(...),
    student_id: int = 1,
    db: Session = Depends(get_db)
):
    """
    Test Layer 4: Receipt ID Structural Anomaly Detection
    
    Upload a receipt image to test:
    - Receipt ID extraction (consensus between EasyOCR + Google Vision)
    - Structural analysis (prefix, pattern, 2-grams)
    - Duplicate detection (exact ID match)
    - Pattern similarity search (90-day sliding window)
    - Risk scoring based on cluster size
    - Retroactive risk updates
    
    Perfect for testing the adaptive pattern learning system!
    """
    
    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save file
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # ===== Run Multi-OCR to get text =====
        ocr_comparison = MultiOCRService.compare_all_ocr(temp_path)
        
        # Get text from both engines
        easyocr_text = ocr_comparison["easyocr"]["raw_text"]
        google_text = ocr_comparison["google_cloud_vision"]["raw_text"]
        
        # ===== Create a temporary receipt record for testing =====
        # In production, this would come from Layer 1-3 processing
        from datetime import datetime
        import uuid
        
        receipt_uuid = str(uuid.uuid4())
        
        # Mock receipt (just for testing Layer 4)
        from .database.models.request import Request as RequestModel, RequestStatus
        test_request = RequestModel(
            student_id=student_id,
            comment="Test Layer 4 - Anomaly Detection",
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
        
        # ===== Mock Layer 3 OCR data (needed for Layer 4 queries) =====
        # Extract receipt ID first
        extracted_id, ocr_conf = AnomalyService.extract_receipt_id_from_ocr(
            easyocr_text,
            google_text
        )
        
        if extracted_id:
            mock_ocr = ReceiptOCR(
                receipt_id=receipt_uuid,
                ocr_engine_used="consensus",
                extracted_receipt_id=extracted_id,
                raw_ocr_text=google_text[:500]
            )
            db.add(mock_ocr)
            db.flush()
        
        # ===== Run Layer 4 Analysis =====
        layer4_result = AnomalyService.analyze_receipt_id(
            db=db,
            receipt_id=receipt_uuid,
            easyocr_text=easyocr_text,
            google_vision_text=google_text
        )
        
        # Commit all changes
        db.commit()
        
        # ===== Build Response =====
        if not layer4_result["success"]:
            return {
                "action": "error",
                "message": f"❌ Layer 4 Error: {layer4_result.get('error', 'Unknown error')}",
                "layer4": layer4_result,
                "receipt_id": receipt_uuid,
                "filename": file.filename
            }
        
        # Interpret results
        assessment = layer4_result["assessment"]
        risk = layer4_result["layer4_risk_score"]
        
        if layer4_result["is_duplicate"]:
            message = f"🚨 DUPLICATE FRAUD: This receipt ID was already submitted! (Original: {layer4_result['original_receipt_id']})"
            action = "rejected_duplicate"
        elif assessment == "validated_cluster":
            message = f"✅ VALIDATED: {layer4_result['similar_pattern_count']+1} receipts share this pattern (LOW RISK)"
            action = "approved_validated"
        elif assessment == "triplet_pattern":
            message = f"⚠️ EMERGING PATTERN: {layer4_result['similar_pattern_count']+1} receipts found (MEDIUM RISK)"
            action = "flagged_medium"
        elif assessment == "pair_pattern":
            message = f"⚠️ PARTIAL VALIDATION: 1 other similar receipt found (MEDIUM-HIGH RISK)"
            action = "flagged_medium_high"
        elif assessment == "solo_pattern":
            message = "🔍 SOLO PATTERN: No similar receipts found - needs validation (HIGH RISK)"
            action = "flagged_high"
        else:
            message = f"⚠️ Assessment: {assessment}"
            action = "flagged"
        
        return {
            "action": action,
            "message": message,
            "receipt_id": receipt_uuid,
            "filename": file.filename,
            
            "layer4_analysis": {
                "extracted_receipt_id": layer4_result["extracted_receipt_id"],
                "ocr_confidence": layer4_result["ocr_confidence"],
                "structure_pattern": layer4_result["structure"],
                
                "duplicate_check": {
                    "is_duplicate": layer4_result["is_duplicate"],
                    "original_receipt_id": layer4_result.get("original_receipt_id")
                },
                
                "pattern_analysis": {
                    "similar_receipts_found": layer4_result["similar_pattern_count"],
                    "assessment": assessment,
                    "cluster_size": layer4_result["similar_pattern_count"] + 1
                },
                
                "anomalies": {
                    "length_anomaly": layer4_result["length_anomaly"],
                    "prefix_rarity_score": layer4_result["prefix_rarity_score"],
                    "digram_rarity_score": layer4_result["digram_rarity_score"]
                },
                
                "risk_score": risk
            },
            
            "ocr_comparison": {
                "easyocr": {
                    "success": ocr_comparison["easyocr"]["success"],
                    "found_receipt_id": extracted_id if ocr_comparison["easyocr"]["success"] else None
                },
                "google_vision": {
                    "success": ocr_comparison["google_cloud_vision"]["success"],
                    "found_receipt_id": extracted_id if ocr_comparison["google_cloud_vision"]["success"] else None
                },
                "consensus_confidence": ocr_conf
            },
            
            "explanation": {
                "what_happened": AnomalyService._get_explanation(layer4_result),
                "why_this_risk": AnomalyService._get_risk_explanation(assessment, risk),
                "next_steps": AnomalyService._get_next_steps(assessment)
            }
        }
        
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()



@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Student Reimbursement Platform API",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "upload_dirs": {
            "receipts": str(settings.RECEIPTS_DIR),
            "documents": str(settings.DOCUMENTS_DIR)
        }
    }

#   cd C:\Users\mehme\student_reimbursement_platform\backend
#   venv\Scripts\activate
#   python -m uvicorn app.main:app --reload
#   API docs (interactive): http://127.0.0.1:8000/docs