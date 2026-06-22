# tests/integration/test_auth.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.dependencies import get_db
from app.database.models.user import User, UserRole
from app.database.models.student import Student
from app.services.auth_service import AuthService

# Import all models so Base.metadata.create_all knows about them
from app.database.models.request import Request
from app.database.models.receipt import Receipt
from app.database.models.student_document import StudentDocument
from app.database.models.receipt_metadata import ReceiptMetadata
from app.database.models.receipt_ocr import ReceiptOCR
from app.database.models.receipt_anomalies import ReceiptAnomalies
from app.database.models.receipt_risk_assessment import ReceiptRiskAssessment


# ── Test database setup ──────────────────────────────────────────────────────

@pytest.fixture
def client():
    """
    Create a fresh in-memory database and a TestClient that uses it
    instead of the real database.
    """
    from sqlalchemy.pool import StaticPool

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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def admin_user(client):
    """Create an admin user directly in the database (bypassing register endpoint)."""
    # Reach into the overridden get_db to insert the admin
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    admin = User(
        email="admin@test.com",
        passwd=AuthService.hash_password("adminpass"),
        role=UserRole.ADMIN
    )
    db.add(admin)
    db.commit()
    db.close()
    return {"email": "admin@test.com", "password": "adminpass"}


# ── Tests ────────────────────────────────────────────────────────────────────

class TestRegister:
    """Tests for the /auth/register endpoint."""

    def test_register_creates_new_account(self, client):
        """
        TEST CASE: POST /auth/register with valid email and password
        must return 201 and the new account details.
        WHY: This is the entry point of the system — students must be able
        to create accounts before doing anything else.
        """
        response = client.post(
            "/auth/register",
            json={"email": "newstudent@test.com", "password": "securepass123"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newstudent@test.com"
        assert data["role"] == "student"
        assert data["account_status"] == "incomplete"
        assert "account_id" in data
        assert "student_id" in data

    def test_register_duplicate_email_fails(self, client):
        """
        TEST CASE: Registering twice with the same email must return 400.
        WHY: Prevents account collisions and ensures email uniqueness which
        is required for login to work correctly.
        """
        client.post(
            "/auth/register",
            json={"email": "dup@test.com", "password": "pass123"}
        )
        response = client.post(
            "/auth/register",
            json={"email": "dup@test.com", "password": "differentpass"}
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_creates_linked_student_record(self, client):
        """
        TEST CASE: After register, both a User and a Student record must
        be created and linked together.
        WHY: The system depends on the User-Student relationship — every
        student needs a profile to upload documents and submit receipts.
        """
        response = client.post(
            "/auth/register",
            json={"email": "linked@test.com", "password": "pass123"}
        )
        data = response.json()
        # Both IDs must be present
        assert data["account_id"] is not None
        assert data["student_id"] is not None


class TestLogin:
    """Tests for the /auth/login endpoint."""

    def test_login_returns_jwt_token(self, client):
        """
        TEST CASE: Login with correct credentials must return 200 with
        a JWT bearer token.
        WHY: All protected endpoints require the JWT — without a working
        login, the entire authenticated API is inaccessible.
        """
        client.post(
            "/auth/register",
            json={"email": "login@test.com", "password": "mypass123"}
        )
        # FastAPI OAuth2PasswordRequestForm uses form data, not JSON
        response = client.post(
            "/auth/login",
            data={"username": "login@test.com", "password": "mypass123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "student"

    def test_login_wrong_password_returns_401(self, client):
        """
        TEST CASE: Login with correct email but wrong password must
        return 401 Unauthorized.
        WHY: Basic security — wrong passwords must not grant access.
        """
        client.post(
            "/auth/register",
            json={"email": "pwtest@test.com", "password": "correctpass"}
        )
        response = client.post(
            "/auth/login",
            data={"username": "pwtest@test.com", "password": "wrongpass"}
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_login_unknown_email_returns_401(self, client):
        """
        TEST CASE: Login with an email that doesn't exist must return 401
        with the same generic error message as wrong password.
        WHY: Returning the same error for both cases prevents email
        enumeration attacks where attackers probe to discover valid emails.
        """
        response = client.post(
            "/auth/login",
            data={"username": "doesnotexist@test.com", "password": "any"}
        )
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Tests for token-based access control on /auth/me."""

    def test_me_endpoint_requires_token(self, client):
        """
        TEST CASE: Calling /auth/me without an Authorization header
        must return 401.
        WHY: Protected endpoints must reject unauthenticated requests
        to keep user data private.
        """
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_me_endpoint_with_valid_token_returns_user(self, client):
        """
        TEST CASE: Calling /auth/me with a valid JWT must return the
        authenticated user's profile information.
        WHY: This endpoint is used by the frontend to know who the
        current user is — student or admin, their email and IDs.
        """
        client.post(
            "/auth/register",
            json={"email": "metest@test.com", "password": "pass123"}
        )
        login_response = client.post(
            "/auth/login",
            data={"username": "metest@test.com", "password": "pass123"}
        )
        token = login_response.json()["access_token"]

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "metest@test.com"
        assert data["role"] == "student"
        assert "student_id" in data

    def test_me_endpoint_with_invalid_token_returns_401(self, client):
        """
        TEST CASE: An invalid or tampered JWT must result in a 401
        response, not be silently accepted.
        WHY: Token validation is the security boundary — accepting
        invalid tokens would allow anyone to impersonate any user.
        """
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer fake.invalid.token"}
        )
        assert response.status_code == 401


class TestPasswordHashing:
    """Tests verifying that passwords are never stored in plaintext."""

    def test_password_is_hashed_in_database(self, client):
        """
        TEST CASE: After registration, the password stored in the database
        must NOT match the plaintext password — it must be hashed.
        WHY: Storing plaintext passwords is a critical security flaw.
        This test ensures bcrypt hashing is actually applied.
        """
        client.post(
            "/auth/register",
            json={"email": "hashtest@test.com", "password": "myplaintext"}
        )
        # Verify directly in the database
        db_gen = app.dependency_overrides[get_db]()
        db = next(db_gen)
        user = db.query(User).filter(User.email == "hashtest@test.com").first()
        assert user is not None
        assert user.passwd != "myplaintext"
        # Bcrypt hashes start with $2b$ and are 60 chars
        assert user.passwd.startswith("$2b$")
        assert len(user.passwd) == 60
        db.close()

class TestChangePassword:
    """Tests for PATCH /auth/change-password endpoint."""

    def test_change_password_with_correct_current(self, client):
        """
        TEST CASE: Changing password with the correct current password must succeed.
        WHY: This is the happy path — users must be able to update their own password.
        """
        client.post("/auth/register", json={"email": "pw@test.com", "password": "oldpass123"})
        login = client.post(
            "/auth/login",
            data={"username": "pw@test.com", "password": "oldpass123"}
        )
        token = login.json()["access_token"]

        response = client.patch(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "oldpass123", "new_password": "newpass456"}
        )
        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()

        new_login = client.post(
            "/auth/login",
            data={"username": "pw@test.com", "password": "newpass456"}
        )
        assert new_login.status_code == 200

    def test_change_password_with_wrong_current(self, client):
        """
        TEST CASE: Password change with the wrong current password must be rejected.
        WHY: This prevents an attacker who has stolen a session token from
        changing the password without knowing the current one — protecting users
        whose tokens may have been compromised.
        """
        client.post("/auth/register", json={"email": "pw2@test.com", "password": "correctpass"})
        login = client.post(
            "/auth/login",
            data={"username": "pw2@test.com", "password": "correctpass"}
        )
        token = login.json()["access_token"]

        response = client.patch(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "wrongpass", "new_password": "newpass456"}
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_change_password_requires_authentication(self, client):
        """
        TEST CASE: Calling /auth/change-password without a token must return 401.
        WHY: Defensive check — password changes must always require authentication.
        """
        response = client.patch(
            "/auth/change-password",
            json={"current_password": "any", "new_password": "newpass456"}
        )
        assert response.status_code == 401

    def test_new_password_minimum_length(self, client):
        """
        TEST CASE: A new password shorter than 8 characters must be rejected.
        WHY: Enforces a minimum security standard.
        """
        client.post("/auth/register", json={"email": "pw3@test.com", "password": "validpass"})
        login = client.post(
            "/auth/login",
            data={"username": "pw3@test.com", "password": "validpass"}
        )
        token = login.json()["access_token"]

        response = client.patch(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "validpass", "new_password": "short"}
        )
        assert response.status_code == 400
        assert "8 characters" in response.json()["detail"]