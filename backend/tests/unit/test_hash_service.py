# tests/unit/test_hash_service.py
import pytest
import tempfile
from pathlib import Path
from app.services.validation.hash_service import HashService
from app.database.models.receipt import Receipt
from app.database.models.request import Request, RequestStatus
from app.database.models.student import Student
from app.database.models.user import User, UserRole


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_file_factory():
    """Create temporary files with specified content for testing."""
    created_files = []

    def _make(content: bytes) -> Path:
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        f.write(content)
        f.close()
        path = Path(f.name)
        created_files.append(path)
        return path

    yield _make

    # Cleanup after test
    for path in created_files:
        if path.exists():
            path.unlink()


@pytest.fixture
def student_a(db_session):
    """Create test student A."""
    user = User(email="a@test.com", passwd="hashed", role=UserRole.STUDENT)
    db_session.add(user)
    db_session.flush()
    student = Student(user_id=user.account_id, email="a@test.com", name="Student A")
    db_session.add(student)
    db_session.commit()
    return student


@pytest.fixture
def student_b(db_session):
    """Create test student B."""
    user = User(email="b@test.com", passwd="hashed", role=UserRole.STUDENT)
    db_session.add(user)
    db_session.flush()
    student = Student(user_id=user.account_id, email="b@test.com", name="Student B")
    db_session.add(student)
    db_session.commit()
    return student


def _create_receipt(db_session, student_id: int, sha256_hash: str):
    """Helper: create a request and receipt with given hash for a student."""
    request = Request(student_id=student_id, status=RequestStatus.PENDING, confirmed=False)
    db_session.add(request)
    db_session.flush()
    receipt = Receipt(
        receipt_id=f"test-{sha256_hash[:8]}",
        student_id=student_id,
        request_id=request.request_id,
        file_path=f"uploads/test/{sha256_hash[:8]}.jpg",
        sha256_hash=sha256_hash
    )
    db_session.add(receipt)
    db_session.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestComputeSha256:
    """Tests for the SHA-256 hash computation."""

    def test_hash_is_deterministic(self, temp_file_factory):
        """
        TEST CASE: Same file content must produce the same hash every time.
        WHY: If the hash changes between calls, the entire duplicate detection
        layer is broken — we could never reliably identify duplicates.
        """
        path = temp_file_factory(b"test receipt content")
        hash1 = HashService.compute_sha256(path)
        hash2 = HashService.compute_sha256(path)
        assert hash1 == hash2

    def test_different_files_produce_different_hashes(self, temp_file_factory):
        """
        TEST CASE: Two files with different content must produce different hashes.
        WHY: Sanity check — if different files produced the same hash, we'd be
        flagging legitimate unique submissions as duplicates.
        """
        path_a = temp_file_factory(b"receipt A content")
        path_b = temp_file_factory(b"receipt B content")
        hash_a = HashService.compute_sha256(path_a)
        hash_b = HashService.compute_sha256(path_b)
        assert hash_a != hash_b

    def test_hash_has_correct_length(self, temp_file_factory):
        """
        TEST CASE: SHA-256 hash should always be 64 hexadecimal characters.
        WHY: Verifies the hash format is consistent — important for database
        column constraints and equality comparisons.
        """
        path = temp_file_factory(b"any content")
        hash_value = HashService.compute_sha256(path)
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)


class TestValidateFileIntegrity:
    """Tests for the full Layer 1 pipeline including database checks."""

    @pytest.mark.asyncio
    async def test_new_unique_file_passes(self, db_session, temp_file_factory, student_a):
        """
        TEST CASE: A brand new file with no matching hash in the database
        should pass through with all fraud flags set to False.
        WHY: The system must not falsely flag legitimate first-time submissions.
        """
        path = temp_file_factory(b"unique new receipt")
        result = await HashService.validate_file_integrity(
            db=db_session, file_path=path, student_id=student_a.student_id
        )
        assert result["is_duplicate"] is False
        assert result["fraud_suspected"] is False
        assert result["sha256_hash"] is not None

    @pytest.mark.asyncio
    async def test_self_duplicate_is_detected(self, db_session, temp_file_factory, student_a):
        """
        TEST CASE: When the same student submits the same file twice,
        the second submission must be flagged as is_duplicate=True
        but fraud_suspected=False (not malicious, just accidental).
        WHY: Self-duplicates are common mistakes — they should be blocked
        but not treated as fraud since the student didn't try to steal another's receipt.
        """
        path = temp_file_factory(b"my receipt content")
        file_hash = HashService.compute_sha256(path)

        # Simulate the first submission already being saved
        _create_receipt(db_session, student_a.student_id, file_hash)

        # Now check what happens on the second submission
        result = await HashService.validate_file_integrity(
            db=db_session, file_path=path, student_id=student_a.student_id
        )
        assert result["is_duplicate"] is True
        assert result["fraud_suspected"] is False

    @pytest.mark.asyncio
    async def test_cross_student_fraud_is_detected(self, db_session, temp_file_factory, student_a, student_b):
        """
        TEST CASE: When student B submits a file that student A already submitted,
        student B's submission must be flagged as fraud_suspected=True.
        WHY: This is the most important security check — it catches a student
        attempting to reuse someone else's receipt for reimbursement.
        """
        path = temp_file_factory(b"shared receipt content")
        file_hash = HashService.compute_sha256(path)

        # Student A submits first
        _create_receipt(db_session, student_a.student_id, file_hash)

        # Student B tries to submit the same file
        result = await HashService.validate_file_integrity(
            db=db_session, file_path=path, student_id=student_b.student_id
        )
        assert result["fraud_suspected"] is True
        assert result["is_global_duplicate"] is True
        assert result["other_student_id"] == student_a.student_id

    @pytest.mark.asyncio
    async def test_hash_field_is_always_returned(self, db_session, temp_file_factory, student_a):
        """
        TEST CASE: The result dict must always contain the sha256_hash field
        regardless of duplicate status.
        WHY: Downstream layers and database storage rely on this field
        always being present — if it's missing the pipeline crashes.
        """
        path = temp_file_factory(b"test content")
        result = await HashService.validate_file_integrity(
            db=db_session, file_path=path, student_id=student_a.student_id
        )
        assert "sha256_hash" in result
        assert len(result["sha256_hash"]) == 64