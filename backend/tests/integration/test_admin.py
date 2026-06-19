# tests/integration/test_admin.py
import pytest
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

# Import remaining models
from app.database.models.receipt import Receipt
from app.database.models.student_document import StudentDocument
from app.database.models.receipt_metadata import ReceiptMetadata
from app.database.models.receipt_ocr import ReceiptOCR
from app.database.models.receipt_anomalies import ReceiptAnomalies
from app.database.models.receipt_risk_assessment import ReceiptRiskAssessment


# ── Test setup ───────────────────────────────────────────────────────────────

@pytest.fixture
def db_and_client():
    """In-memory database shared with the FastAPI test client."""
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
def admin_token(db_and_client):
    """Create an admin user and return their auth token."""
    db, client = db_and_client
    admin = User(
        email="admin@test.com",
        passwd=AuthService.hash_password("adminpass"),
        role=UserRole.ADMIN
    )
    db.add(admin)
    db.commit()
    login = client.post(
        "/auth/login",
        data={"username": "admin@test.com", "password": "adminpass"}
    )
    return login.json()["access_token"]


@pytest.fixture
def student_token(db_and_client):
    """Create a regular student and return their auth token."""
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
        account_status=AccountStatus.APPROVED
    )
    db.add(student)
    db.commit()
    login = client.post(
        "/auth/login",
        data={"username": "student@test.com", "password": "studentpass"}
    )
    return login.json()["access_token"]


def _create_pending_student(db, email="pending@test.com"):
    """Create a student awaiting admin approval."""
    user = User(email=email, passwd="hashed", role=UserRole.STUDENT)
    db.add(user)
    db.flush()
    # Use email prefix to ensure unique stpt_id across test fixtures
    unique_suffix = email.split("@")[0]
    student = Student(
        user_id=user.account_id,
        email=email,
        name="Pending Student",
        stpt_id=f"stpt_{unique_suffix}",
        iban=f"RO12RNCB{unique_suffix}",
        account_status=AccountStatus.PENDING_APPROVAL,
    )
    db.add(student)
    db.commit()
    return student


# ── Authorization tests ──────────────────────────────────────────────────────

class TestAdminAuthorization:
    """Tests verifying that admin endpoints reject non-admin access."""

    def test_student_cannot_access_admin_endpoints(self, db_and_client, student_token):
        """
        TEST CASE: A student attempting to access /admin/students must
        receive a 403 Forbidden response.
        WHY: Students must never see all other students' data. Role-based
        access control is critical for privacy and data protection.
        """
        _, client = db_and_client
        response = client.get(
            "/admin/students",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 403

    def test_unauthenticated_cannot_access_admin_endpoints(self, db_and_client):
        """
        TEST CASE: Requests with no token must be rejected with 401.
        WHY: Admin endpoints expose sensitive data — they must require
        authentication before any role check.
        """
        _, client = db_and_client
        response = client.get("/admin/students")
        assert response.status_code == 401

    def test_admin_can_access_admin_endpoints(self, db_and_client, admin_token):
        """
        TEST CASE: An admin user must be able to access /admin/students.
        WHY: Confirms the authorization logic correctly permits admins,
        not just blocks non-admins.
        """
        _, client = db_and_client
        response = client.get(
            "/admin/students",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200


# ── List & view students ─────────────────────────────────────────────────────

class TestListStudents:
    """Tests for GET /admin/students."""

    def test_list_returns_all_students(self, db_and_client, admin_token):
        """
        TEST CASE: GET /admin/students must return all students in the database.
        WHY: Admin needs a complete view of all student accounts to manage them.
        """
        db, client = db_and_client
        _create_pending_student(db, "s1@test.com")
        _create_pending_student(db, "s2@test.com")
        _create_pending_student(db, "s3@test.com")

        response = client.get(
            "/admin/students",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        # Note: student_token fixture also creates one student
        assert len(response.json()) >= 3

    def test_list_filters_by_status(self, db_and_client, admin_token):
        """
        TEST CASE: The status query parameter must filter students by
        account_status.
        WHY: Admin uses status filters (pending/approved/rejected) to
        prioritize their review queue.
        """
        db, client = db_and_client
        _create_pending_student(db, "pending1@test.com")
        _create_pending_student(db, "pending2@test.com")
        # Approved student
        user = User(email="approved@test.com", passwd="hash", role=UserRole.STUDENT)
        db.add(user)
        db.flush()
        s = Student(
            user_id=user.account_id,
            email="approved@test.com",
            account_status=AccountStatus.APPROVED
        )
        db.add(s)
        db.commit()

        response = client.get(
            "/admin/students?status=pending_approval",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        for student in data:
            assert student["account_status"] == "pending_approval"

    def test_invalid_status_filter_returns_400(self, db_and_client, admin_token):
        """
        TEST CASE: An invalid status filter must return 400 with an
        explanation of valid values.
        WHY: Defensive input validation — informs clients of valid options
        instead of silently returning unexpected results.
        """
        _, client = db_and_client
        response = client.get(
            "/admin/students?status=invalid",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400


class TestGetStudent:
    """Tests for GET /admin/students/{student_id}."""

    def test_get_student_returns_full_details(self, db_and_client, admin_token):
        """
        TEST CASE: GET /admin/students/{id} must return the student's
        profile plus all their uploaded documents.
        WHY: Admin needs to verify documents (student ID, STPT card, bank
        proof) before approving an account.
        """
        db, client = db_and_client
        student = _create_pending_student(db)

        response = client.get(
            f"/admin/students/{student.student_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == student.student_id
        assert data["email"] == student.email
        assert data["name"] == "Pending Student"
        assert "documents" in data

    def test_get_nonexistent_student_returns_404(self, db_and_client, admin_token):
        """
        TEST CASE: Requesting a student_id that doesn't exist must
        return 404.
        WHY: Defensive handling of bad input.
        """
        _, client = db_and_client
        response = client.get(
            "/admin/students/99999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404


# ── Student account decisions ────────────────────────────────────────────────

class TestDecideStudentAccount:
    """Tests for PATCH /admin/students/{id}/decision."""

    def test_approve_pending_student(self, db_and_client, admin_token):
        """
        TEST CASE: Admin approving a pending student must change their
        account_status to APPROVED.
        WHY: This is the gate that lets new students start submitting
        receipts — must work correctly.
        """
        db, client = db_and_client
        student = _create_pending_student(db)

        response = client.patch(
            f"/admin/students/{student.student_id}/decision",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": "approve", "note": "All documents verified"}
        )
        assert response.status_code == 200
        assert response.json()["new_status"] == "approved"

        db.refresh(student)
        assert student.account_status == AccountStatus.APPROVED

    def test_reject_pending_student(self, db_and_client, admin_token):
        """
        TEST CASE: Admin rejecting a pending student must set status
        to REJECTED.
        WHY: Rejection is the alternative path — students with invalid
        documents must be blocked from submitting receipts.
        """
        db, client = db_and_client
        student = _create_pending_student(db)

        response = client.patch(
            f"/admin/students/{student.student_id}/decision",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": "reject", "note": "Invalid STPT card photo"}
        )
        assert response.status_code == 200
        db.refresh(student)
        assert student.account_status == AccountStatus.REJECTED

    def test_cannot_decide_non_pending_student(self, db_and_client, admin_token):
        """
        TEST CASE: Trying to decide an already-approved or already-rejected
        student must return 400.
        WHY: Decisions should only happen once. Re-deciding could create
        confusion in audit logs and student communications.
        """
        db, client = db_and_client
        student = _create_pending_student(db)
        student.account_status = AccountStatus.APPROVED
        db.commit()

        response = client.patch(
            f"/admin/students/{student.student_id}/decision",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": "reject"}
        )
        assert response.status_code == 400

    def test_invalid_decision_returns_400(self, db_and_client, admin_token):
        """
        TEST CASE: A decision value other than 'approve' or 'reject' must
        return 400.
        WHY: Input validation prevents malformed requests from corrupting
        the account state.
        """
        db, client = db_and_client
        student = _create_pending_student(db)

        response = client.patch(
            f"/admin/students/{student.student_id}/decision",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": "maybe"}
        )
        assert response.status_code == 400


# ── Edit student ─────────────────────────────────────────────────────────────

class TestEditStudent:
    """Tests for PATCH /admin/students/{id}/edit."""

    def test_admin_can_update_student_fields(self, db_and_client, admin_token):
        """
        TEST CASE: Admin must be able to update a student's name, IBAN,
        and STPT ID.
        WHY: Admins fix typos and update student records on behalf of
        students — this is a common administrative task.
        """
        db, client = db_and_client
        student = _create_pending_student(db)

        response = client.patch(
            f"/admin/students/{student.student_id}/edit",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Updated Name",
                "iban": "RO99NEW9999999999",
                "stpt_id": "99999"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["iban"] == "RO99NEW9999999999"
        assert data["stpt_id"] == "99999"

    def test_partial_update_only_changes_provided_fields(self, db_and_client, admin_token):
        """
        TEST CASE: When only one field is provided in the payload, only
        that field must be updated. Other fields must remain unchanged.
        WHY: Admins often want to fix just one field without re-entering
        everything else.
        """
        db, client = db_and_client
        student = _create_pending_student(db)
        original_iban = student.iban

        response = client.patch(
            f"/admin/students/{student.student_id}/edit",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Only Name Changed"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Only Name Changed"
        assert response.json()["iban"] == original_iban


# ── Request list & decisions ─────────────────────────────────────────────────

class TestListRequests:
    """Tests for GET /admin/requests."""

    def test_list_returns_only_confirmed_requests(self, db_and_client, admin_token):
        """
        TEST CASE: The admin requests list must include only confirmed
        requests, not unconfirmed drafts.
        WHY: Unconfirmed requests are drafts the student is still working
        on. Admin should not see them in their review queue.
        """
        db, client = db_and_client
        student = _create_pending_student(db)
        # One confirmed and one unconfirmed
        db.add(Request(student_id=student.student_id, status=RequestStatus.PENDING, confirmed=True))
        db.add(Request(student_id=student.student_id, status=RequestStatus.PENDING, confirmed=False))
        db.commit()

        response = client.get(
            "/admin/requests",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        for req in data:
            assert req["confirmed"] is True


class TestDecideRequest:
    """Tests for PATCH /admin/requests/{id}/decision."""

    def test_approve_request(self, db_and_client, admin_token):
        """
        TEST CASE: Admin approving a pending request must set the
        request status to APPROVED and record review_timestamp.
        WHY: This is the primary admin action — determines whether a
        student receives reimbursement.
        """
        db, client = db_and_client
        student = _create_pending_student(db)
        request = Request(
            student_id=student.student_id,
            status=RequestStatus.PENDING,
            confirmed=True
        )
        db.add(request)
        db.commit()

        response = client.patch(
            f"/admin/requests/{request.request_id}/decision",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": "approve", "note": "Approved for reimbursement"}
        )
        assert response.status_code == 200
        db.refresh(request)
        assert request.status == RequestStatus.APPROVED
        assert request.admin_feedback == "Approved for reimbursement"

    def test_reject_request_with_feedback(self, db_and_client, admin_token):
        """
        TEST CASE: Admin rejecting a request must save the feedback message
        so the student understands the rejection.
        WHY: Feedback enables transparency. Students need to know why their
        request was denied to potentially resubmit correctly.
        """
        db, client = db_and_client
        student = _create_pending_student(db)
        request = Request(
            student_id=student.student_id,
            status=RequestStatus.PENDING,
            confirmed=True
        )
        db.add(request)
        db.commit()

        response = client.patch(
            f"/admin/requests/{request.request_id}/decision",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": "reject", "note": "STPT ID mismatch"}
        )
        assert response.status_code == 200
        assert response.json()["admin_feedback"] == "STPT ID mismatch"

    def test_decide_nonexistent_request_returns_400(self, db_and_client, admin_token):
        """
        TEST CASE: Deciding a request_id that does not exist must return 400.
        WHY: Defensive handling of bad input prevents URL tampering or
        stale frontend state from crashing the backend.
        """
        _, client = db_and_client
        response = client.patch(
            "/admin/requests/99999/decision",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": "approve"}
        )
        assert response.status_code == 400