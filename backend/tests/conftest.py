# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.base import Base

# Import all models so SQLAlchemy registers them
from app.database.models.user import User
from app.database.models.student import Student
from app.database.models.request import Request
from app.database.models.receipt import Receipt
from app.database.models.student_document import StudentDocument
from app.database.models.receipt_metadata import ReceiptMetadata
from app.database.models.receipt_ocr import ReceiptOCR
from app.database.models.receipt_anomalies import ReceiptAnomalies
from app.database.models.receipt_risk_assessment import ReceiptRiskAssessment


@pytest.fixture
def db_session():
    """
    Provide a clean in-memory SQLite database for each test.
    The database is destroyed at the end of the test.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()