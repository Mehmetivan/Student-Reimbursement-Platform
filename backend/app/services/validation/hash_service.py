# app/services/validation/hash_service.py
import hashlib
from pathlib import Path
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from ...database.models.receipt import Receipt

class HashService:
    """Layer 1: File Integrity & Duplication Detection"""
    
    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute SHA-256 hash of a file"""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    @staticmethod
    def check_duplicate(db: Session, file_hash: str, student_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if file hash already exists in database
        Returns: (is_duplicate, existing_receipt_id)
        """
        existing_receipt = db.query(Receipt).filter(
            Receipt.sha256_hash == file_hash,
            Receipt.student_id == student_id
        ).first()
        
        if existing_receipt:
            return True, existing_receipt.receipt_id
        
        return False, None
    
    @staticmethod
    def check_global_duplicate(db: Session, file_hash: str) -> Tuple[bool, Optional[int]]:
        """
        Check if file hash exists across ALL students (potential fraud)
        Returns: (is_duplicate, other_student_id)
        """
        existing_receipt = db.query(Receipt).filter(
            Receipt.sha256_hash == file_hash
        ).first()
        
        if existing_receipt:
            return True, existing_receipt.student_id
        
        return False, None
    
    @staticmethod
    async def validate_file_integrity(
        db: Session, 
        file_path: Path, 
        student_id: int
    ) -> dict:
        """
        Complete Layer 1 validation
        Returns validation result with hash and duplicate status
        """
        file_hash = HashService.compute_sha256(file_path)
        
        # Check for duplicates within student's own submissions
        is_dup, dup_receipt_id = HashService.check_duplicate(db, file_hash, student_id)
        
        # Check for global duplicates (fraud detection)
        is_global_dup, other_student_id = HashService.check_global_duplicate(db, file_hash)
        
        result = {
            "sha256_hash": file_hash,
            "is_duplicate": is_dup,
            "duplicate_receipt_id": dup_receipt_id,
            "is_global_duplicate": is_global_dup and other_student_id != student_id,
            "fraud_suspected": is_global_dup and other_student_id != student_id,
            "other_student_id": other_student_id if is_global_dup else None
        }
        
        return result