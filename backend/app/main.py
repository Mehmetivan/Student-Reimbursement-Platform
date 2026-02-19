# app/main.py
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
from .database.models.receipt_metadata import ReceiptMetadata
from .database.models.student_document import StudentDocument
from .services.validation.exif_service import ExifService
from .services.validation.ocr_service import OCRService

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


@app.post("/test/combined-layers")
async def test_combined_layers(
    file: UploadFile = File(...),
    student_id: int = 1,
    db: Session = Depends(get_db)
):
    """
    Test Layer 1 + Layer 2 Combined with Database Save
    
    Upload a file to test complete validation:
    - Layer 1: Hash & duplicate detection
    - Layer 2: EXIF analysis
    - Combined risk assessment
    - Saves to database (receipts + receipt_metadata tables)
    """
    
    # Save uploaded file temporarily
    temp_path = Path("uploads") / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save file
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # ===== LAYER 1: Hash validation =====
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
        
        # ===== Layer 1 PASSED - Save to database =====
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
        
        # ===== LAYER 2: EXIF analysis =====
        layer2_result = ExifService.analyze_exif(permanent_path)
        
        # Save Layer 2 results to database
        from .services.metadata_service import MetadataService
        
        metadata = MetadataService.save_layer2_results(
            db=db,
            receipt_id=receipt_uuid,
            layer2_analysis=layer2_result
        )
        
        # Update combined risk score
        MetadataService.update_combined_risk_score(
            db=db,
            receipt_id=receipt_uuid,
            layer1_fraud=layer1_result["fraud_suspected"],
            layer1_duplicate=layer1_result["is_duplicate"]
        )
        
        db.commit()
        
        # ===== Calculate combined risk =====
        total_risk = layer2_result["risk_score"]
        
        # Decision logic
        if total_risk >= 0.8:
            action = "flagged_high_risk"
            message = "🚨 HIGH RISK: Receipt saved but flagged for admin review"
        elif total_risk >= 0.5:
            action = "flagged_medium_risk"
            message = "⚠️ MEDIUM RISK: Receipt saved but flagged for admin review"
        else:
            action = "approved"
            message = "✅ APPROVED: Receipt passed all validation checks"
        
        # Final response
        return {
            "filename": file.filename,
            "student_id": student_id,
            "receipt_id": receipt_uuid,
            "file_location": relative_file_path,
            "action": action,
            "message": message,
            
            "layer1": {
                "sha256_hash": layer1_result["sha256_hash"],
                "is_duplicate": layer1_result["is_duplicate"],
                "fraud_suspected": layer1_result["fraud_suspected"]
            },
            
            "layer2": {
                "exif_status": layer2_result["exif_status"],
                "has_editing_software": layer2_result["has_editing_software"],
                "editing_software": layer2_result.get("editing_software"),
                "is_mobile_camera": layer2_result["is_mobile_camera"],
                "camera_model": layer2_result["camera_model"],
                "flags": layer2_result["flags"],
                "risk_score": layer2_result["risk_score"],
                "assessment": layer2_result["assessment"]
            },
            
            "combined_risk_score": min(total_risk, 1.0),
            "database_saved": True
        }
        
    finally:
        # Clean up temp file
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