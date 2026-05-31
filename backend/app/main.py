# app/main.py
import multiprocessing
multiprocessing.set_start_method('spawn', force=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database.base import Base
from .database.session import engine

# Import all models so SQLAlchemy registers them before create_all
from .database.models.receipt import Receipt
from .database.models.receipt_anomalies import ReceiptAnomalies
from .database.models.receipt_metadata import ReceiptMetadata
from .database.models.receipt_ocr import ReceiptOCR
from .database.models.receipt_risk_assessment import ReceiptRiskAssessment
from .database.models.request import Request
from .database.models.student import Student
from .database.models.student_document import StudentDocument
from .database.models.user import User

# Routers
from .routers import auth, students, admin, receipts, test_routes

from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(
    title="Student Reimbursement Platform",
    description="Multi-layer fraud detection system for public transport reimbursements",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


# Serve uploaded files statically
os.makedirs(settings.RECEIPTS_DIR, exist_ok=True)
os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(admin.router)
app.include_router(receipts.router)
app.include_router(test_routes.router)

# ── Health endpoints ──────────────────────────────────────────────────────────

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

# ── Run instructions ──────────────────────────────────────────────────────────
#   cd backend
#   venv\Scripts\activate          (Windows)
#   source venv/bin/activate       (Mac/Linux)
#   python -m uvicorn app.main:app --reload
#   Swagger UI: http://127.0.0.1:8000/docs

#   cd frontend && npm run dev
#   http://localhost:3000

