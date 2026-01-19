from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import os
from app.database.session import get_db
from app.services.validation.hash_service import compute_sha256
from app.database.models.receipt import Receipt
from app.config import settings

router = APIRouter(prefix="/receipts", tags=["receipts"])

@router.post("/upload")
def upload_receipt(student_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Save file
    os.makedirs(settings.RECEIPT_UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.RECEIPT_UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(file.file.read())

    # Compute hash
    file_hash = compute_sha256(file_path)

    # Check duplicates
    existing = db.query(Receipt).filter(Receipt.sha256_hash == file_hash).first()
    if existing:
        raise HTTPException(status_code=400, detail="Duplicate receipt detected")

    # Save in DB
    receipt = Receipt(
        student_id=student_id,
        file_path=file_path,
        sha256_hash=file_hash
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    return {"receipt_id": receipt.receipt_id, "sha256_hash": file_hash}
