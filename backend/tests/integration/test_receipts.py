# tests/integration/test_receipts.py
import pytest
from unittest.mock import AsyncMock, patch
from io import BytesIO
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.dependencies import get_db
from app.services.auth_service import AuthService
from app.database.models.user import User, UserRole
from app.database.models.student import Student, AccountStatus
from app.database.models.request import Request, RequestStatus
from app.database.models.receipt import Receipt

# Import all models so Base.metadata.create_all knows about them
from app.database.models.student_document import StudentDocument
from app.database.models.receipt_metadata import ReceiptMetadata
from app.database.models.receipt_ocr import ReceiptOCR
from app.database.models.receipt_anomalies import ReceiptAnomalies
from app.database.models.receipt_risk_assessment import ReceiptRiskAssessment


# Test setup

@pytest.fixture
def db_and_client():
    """Provide an in-memory database AND a TestClient sharing the same engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    db = TestSessionLocal()
    yield db, client
    db.close()
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def approved_student(db_and_client):
    """Create an APPROVED student and return their auth token + student record."""
    db, client = db_and_client
    user = User(
        email="student@test.com",
        passwd=AuthService.hash_password("studentpass"),
        role=UserRole.STUDENT
    )
    db.add(user)
    db.flush()
    student = Student(
        user_id=user.account_id,
        email="student@test.com",
        name="Test Student",
        stpt_id="00555845",
        iban="RO12RNCB0123456789012345",
        account_status=AccountStatus.APPROVED
    )
    db.add(student)
    db.commit()

    # Login to get a token
    login_response = client.post(
        "/auth/login",
        data={"username": "student@test.com", "password": "studentpass"}
    )
    token = login_response.json()["access_token"]
    return {"token": token, "student_id": student.student_id, "db": db, "client": client}


@pytest.fixture
def incomplete_student(db_and_client):
    """Create an INCOMPLETE student, should NOT be able to submit receipts."""
    db, client = db_and_client
    user = User(
        email="incomplete@test.com",
        passwd=AuthService.hash_password("pass"),
        role=UserRole.STUDENT
    )
    db.add(user)
    db.flush()
    student = Student(
        user_id=user.account_id,
        email="incomplete@test.com",
        account_status=AccountStatus.INCOMPLETE
    )
    db.add(student)
    db.commit()

    login_response = client.post(
        "/auth/login",
        data={"username": "incomplete@test.com", "password": "pass"}
    )
    token = login_response.json()["access_token"]
    return {"token": token, "client": client}


def _fake_pipeline_result(request_id=1, receipt_id="fake-uuid", action="approved"):
    """Generate a fake pipeline result that creates a request in the test DB."""
    return {
        "action": action,
        "message": "Test pipeline result",
        "receipt_id": receipt_id,
        "request_id": request_id,
        "ocr_summary": {
            "stpt_id_found": True,
            "stpt_id_matches": True,
            "receipt_id_found": True,
        },
        "final_assessment": {
            "total_risk_score": 0.1,
            "assessment": "low_risk"
        },
        "confirmed": False,
    }


def _make_test_image() -> tuple[str, BytesIO, str]:
    """Make a minimal in-memory JPEG for upload tests."""
    from PIL import Image
    img = Image.new('RGB', (10, 10), color='red')
    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return ("test.jpg", buf, "image/jpeg")


# Submit endpoint tests

class TestSubmitReceipt:
    """Tests for POST /receipts/submit."""

    def test_approved_student_can_submit(self, approved_student):
        """
        TEST CASE: An approved student must be able to submit a receipt
        and receive a 200 with the pipeline result.
        WHY: This is the primary student action, submitting a receipt
        for reimbursement. Without this working, the system is unusable.
        """
        token = approved_student["token"]
        client = approved_student["client"]
        db = approved_student["db"]
        student_id = approved_student["student_id"]

        # Create a real request in the DB so the fake pipeline result
        # can reference an existing request_id
        request = Request(student_id=student_id, status=RequestStatus.PENDING, confirmed=False)
        db.add(request)
        db.commit()

        fake_result = _fake_pipeline_result(request_id=request.request_id)

        with patch("app.routers.receipts.ReceiptService.run_full_pipeline",
                   new_callable=AsyncMock, return_value=fake_result):
            filename, file_buf, content_type = _make_test_image()
            response = client.post(
                "/receipts/submit",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (filename, file_buf, content_type)},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "approved"
        assert data["confirmed"] is False

    def test_incomplete_student_cannot_submit(self, incomplete_student):
        """
        TEST CASE: A student whose account is INCOMPLETE must receive 403
        when trying to submit a receipt.
        WHY: Students must complete their profile (ID, STPT card, bank proof)
        before submitting receipts. This guards the system from incomplete
        data and uploaded receipts from unverified accounts.
        """
        token = incomplete_student["token"]
        client = incomplete_student["client"]

        filename, file_buf, content_type = _make_test_image()
        response = client.post(
            "/receipts/submit",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, file_buf, content_type)},
        )
        assert response.status_code == 403
        assert "complete your profile" in response.json()["detail"].lower()

    def test_unauthenticated_submit_fails(self, db_and_client):
        """
        TEST CASE: Submitting without an auth token must return 401.
        WHY: Receipt submission is a privileged operation, only logged-in
        students can do it.
        """
        _, client = db_and_client
        filename, file_buf, content_type = _make_test_image()
        response = client.post(
            "/receipts/submit",
            files={"file": (filename, file_buf, content_type)},
        )
        assert response.status_code == 401

    def test_invalid_file_extension_rejected(self, approved_student):
        """
        TEST CASE: A file with disallowed extension (e.g. .txt) must return 400.
        WHY: Only image files should be accepted. Allowing other types could
        lead to security issues or downstream pipeline failures.
        """
        token = approved_student["token"]
        client = approved_student["client"]

        response = client.post(
            "/receipts/submit",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("malicious.txt", BytesIO(b"not an image"), "text/plain")},
        )
        assert response.status_code == 400


# Confirm endpoint tests

class TestConfirmReceipt:
    """Tests for PATCH /receipts/confirm/{request_id}."""

    def test_confirm_unconfirmed_request(self, approved_student):
        """
        TEST CASE: A student must be able to confirm their own unconfirmed
        pending request, making it visible to admin.
        WHY: This is the key step in the confirmation workflow — without it
        no receipt ever reaches admin review.
        """
        token = approved_student["token"]
        client = approved_student["client"]
        db = approved_student["db"]
        student_id = approved_student["student_id"]

        request = Request(student_id=student_id, status=RequestStatus.PENDING, confirmed=False)
        db.add(request)
        db.commit()

        response = client.patch(
            f"/receipts/confirm/{request.request_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "confirmed" in response.json()["message"].lower()

        # Verify in the database
        db.refresh(request)
        assert request.confirmed is True

    def test_cannot_confirm_already_confirmed(self, approved_student):
        """
        TEST CASE: Trying to confirm a request that is already confirmed
        must return 400.
        WHY: Once a request is sent to admin, the student cannot modify it.
        This prevents duplicate confirmations from re-triggering admin
        notifications or other side effects.
        """
        token = approved_student["token"]
        client = approved_student["client"]
        db = approved_student["db"]
        student_id = approved_student["student_id"]

        request = Request(student_id=student_id, status=RequestStatus.PENDING, confirmed=True)
        db.add(request)
        db.commit()

        response = client.patch(
            f"/receipts/confirm/{request.request_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert "already confirmed" in response.json()["detail"].lower()

    def test_cannot_confirm_others_request(self, approved_student, db_and_client):
        """
        TEST CASE: A student must not be able to confirm a request belonging
        to a different student. Should return 404.
        WHY: Access control, students should only be able to manage their
        own submissions. Allowing confirmation of others' requests would
        be a severe authorization bug.
        """
        token = approved_student["token"]
        client = approved_student["client"]
        db = approved_student["db"]

        # Create a second student with a request
        other_user = User(
            email="other@test.com",
            passwd=AuthService.hash_password("pass"),
            role=UserRole.STUDENT
        )
        db.add(other_user)
        db.flush()
        other_student = Student(
            user_id=other_user.account_id,
            email="other@test.com",
            account_status=AccountStatus.APPROVED
        )
        db.add(other_student)
        db.flush()
        other_request = Request(
            student_id=other_student.student_id,
            status=RequestStatus.PENDING,
            confirmed=False
        )
        db.add(other_request)
        db.commit()

        # First student tries to confirm second student's request
        response = client.patch(
            f"/receipts/confirm/{other_request.request_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_confirm_nonexistent_request(self, approved_student):
        """
        TEST CASE: Confirming a request_id that doesn't exist must return 404.
        WHY: Defensive handling of bad input, frontend bugs or URL tampering
        should not crash the backend.
        """
        token = approved_student["token"]
        client = approved_student["client"]

        response = client.patch(
            "/receipts/confirm/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


# Resubmit endpoint tests

class TestResubmitReceipt:
    """Tests for PATCH /receipts/resubmit/{request_id}."""

    def test_cannot_resubmit_confirmed_request(self, approved_student):
        """
        TEST CASE: Once a request is confirmed and sent to admin, the student
        must not be able to replace its receipt, should return 400.
        WHY: Replacing a confirmed receipt would let students change their
        submission after admin has already started reviewing it. This breaks
        the audit trail.
        """
        token = approved_student["token"]
        client = approved_student["client"]
        db = approved_student["db"]
        student_id = approved_student["student_id"]

        request = Request(student_id=student_id, status=RequestStatus.PENDING, confirmed=True)
        db.add(request)
        db.commit()

        filename, file_buf, content_type = _make_test_image()
        response = client.patch(
            f"/receipts/resubmit/{request.request_id}",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, file_buf, content_type)},
        )
        assert response.status_code == 400
        assert "confirmed" in response.json()["detail"].lower()

    def test_cannot_resubmit_decided_request(self, approved_student):
        """
        TEST CASE: A request that has been approved or rejected by admin
        cannot be resubmitted, should return 400.
        WHY: Once a request has a final decision, it's closed. Students must
        submit a new request rather than modify an already-decided one.
        """
        token = approved_student["token"]
        client = approved_student["client"]
        db = approved_student["db"]
        student_id = approved_student["student_id"]

        request = Request(student_id=student_id, status=RequestStatus.APPROVED, confirmed=True)
        db.add(request)
        db.commit()

        filename, file_buf, content_type = _make_test_image()
        response = client.patch(
            f"/receipts/resubmit/{request.request_id}",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, file_buf, content_type)},
        )
        assert response.status_code == 400


