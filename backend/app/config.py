# app/config.py
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./student_reimbursement.db"
    
    # JWT & Security
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # File Storage
    UPLOAD_DIR: Path = Path("uploads")
    RECEIPTS_DIR: Path = UPLOAD_DIR / "receipts"
    DOCUMENTS_DIR: Path = UPLOAD_DIR / "student_documents"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_IMAGE_EXTENSIONS: set = {".jpg", ".jpeg", ".png", ".pdf"}
    
    # Security Thresholds
    DUPLICATE_HASH_THRESHOLD: float = 0.9
    TAMPERING_SCORE_THRESHOLD: float = 0.7
    OCR_CONFIDENCE_THRESHOLD: float = 0.6
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Create upload directories if they don't exist
settings.RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
settings.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)