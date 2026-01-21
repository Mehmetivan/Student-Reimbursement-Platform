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
    
    #additional layers will be added as the project progesses. Only layer 1 at the moment


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