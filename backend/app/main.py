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

app = FastAPI(
    title="Student Reimbursement Platform",
    description="Multi-layer fraud detection system for public transport reimbursements",
    version="1.0.0"
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all database tables
Base.metadata.create_all(bind=engine)

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