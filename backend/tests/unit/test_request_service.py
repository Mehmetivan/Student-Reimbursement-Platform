# tests/unit/test_request_service.py
import pytest
from datetime import datetime, timedelta
from app.services.request_service import RequestService
from app.database.models.user import User, UserRole
from app.database.models.student import Student
from app.database.models.request import Request, RequestStatus
from app.database.models.receipt import Receipt
from app.database.models.receipt_risk_assessment import ReceiptRiskAssessment


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_student(db, email="s@test.com"):
    """Create a student and return their record."""
    user = User(email=email, passwd="hashed", role=UserRole.STUDENT)
    db.add(user)
    db.flush()
    student = Student(user_id=user.account_id, email=email, name="Test")
    db.add(student)
    db.commit()
    return student


def _create_request(db, student_id, status=RequestStatus.PENDING, confirmed=True,
                    submit_timestamp=None, comment=None):
    """Create a request with optional configuration."""
    request = Request(
        student_id=student_id,
        status=status,
        confirmed=confirmed,
        comment=comment,
        submit_timestamp=submit_timestamp or datetime.utcnow(),
    )
    db.add(request)
    db.commit()
    return request


def _create_receipt_with_risk(db, request_id, student_id, total_risk=0.5, assessment="medium_risk"):
    """Create a receipt with an associated risk assessment."""
    receipt = Receipt(
        receipt_id=f"uuid-{request_id}",
        student_id=student_id,
        request_id=request_id,
        file_path=f"uploads/test/{request_id}.jpg",
        sha256_hash=f"hash_{request_id}",
    )
    db.add(receipt)
    db.flush()
    risk = ReceiptRiskAssessment(
        receipt_id=receipt.receipt_id,
        total_risk_score=total_risk,
        assessment=assessment,
        layer1_risk=0.0,
        layer2_risk=0.1,
        layer3_risk=0.0,
        layer4_risk=0.2,
        risk_factors={"total_risk": total_risk, "assessment": assessment},
    )
    db.add(risk)
    db.commit()
    return receipt


# ── Tests ────────────────────────────────────────────────────────────────────

class TestFormatRequest:
    """Tests for the _format_request helper."""

    def test_format_includes_all_basic_fields(self, db_session):
        """
        TEST CASE: The formatted dict must include all fields the frontend needs.
        WHY: The frontend ReimbursementRequest type expects specific fields —
        missing fields would cause display bugs in the request list and detail pages.
        """
        student = _create_student(db_session)
        request = _create_request(db_session, student.student_id, comment="test comment")
        result = RequestService._format_request(request)
        assert "request_id" in result
        assert "student_id" in result
        assert "status" in result
        assert "comment" in result
        assert "admin_feedback" in result
        assert "submit_timestamp" in result
        assert "review_timestamp" in result
        assert "confirmed" in result
        assert "resubmission_count" in result
        assert "receipts" in result
        assert result["comment"] == "test comment"

    def test_format_without_fraud_details_excludes_risk_assessment(self, db_session):
        """
        TEST CASE: When include_fraud_details=False, receipt entries must
        NOT contain risk_assessment data.
        WHY: Students should not see their own fraud risk scores. Only admins
        get the full fraud breakdown in their request views.
        """
        student = _create_student(db_session)
        request = _create_request(db_session, student.student_id)
        _create_receipt_with_risk(db_session, request.request_id, student.student_id)
        db_session.refresh(request)

        result = RequestService._format_request(request, include_fraud_details=False)
        assert len(result["receipts"]) == 1
        assert "risk_assessment" not in result["receipts"][0]

    def test_format_with_fraud_details_includes_risk_assessment(self, db_session):
        """
        TEST CASE: When include_fraud_details=True, receipt entries must
        contain the full risk_assessment data.
        WHY: Admin views need the complete fraud breakdown to make informed
        approval decisions. Each layer score and factor must be visible.
        """
        student = _create_student(db_session)
        request = _create_request(db_session, student.student_id)
        _create_receipt_with_risk(db_session, request.request_id, student.student_id, total_risk=0.85)
        db_session.refresh(request)

        result = RequestService._format_request(request, include_fraud_details=True)
        risk = result["receipts"][0]["risk_assessment"]
        assert risk["total_risk_score"] == 0.85
        assert "layer1_risk" in risk
        assert "layer2_risk" in risk
        assert "layer3_risk" in risk
        assert "layer4_risk" in risk
        assert "risk_factors" in risk


class TestGetStudentRequests:
    """Tests for retrieving a student's own requests."""

    def test_returns_only_own_requests(self, db_session):
        """
        TEST CASE: A student must only see their own requests, not
        other students' requests.
        WHY: Privacy — students must not be able to see receipts or
        submission details belonging to other students.
        """
        s1 = _create_student(db_session, "s1@test.com")
        s2 = _create_student(db_session, "s2@test.com")
        _create_request(db_session, s1.student_id)
        _create_request(db_session, s1.student_id)
        _create_request(db_session, s2.student_id)

        results = RequestService.get_student_requests(db_session, s1.student_id)
        assert len(results) == 2
        for r in results:
            assert r["student_id"] == s1.student_id

    def test_returns_both_confirmed_and_unconfirmed(self, db_session):
        """
        TEST CASE: The student view must show both confirmed and
        unconfirmed (draft) requests.
        WHY: Students need to see their drafts to confirm them. Only the
        admin view filters out unconfirmed requests.
        """
        student = _create_student(db_session)
        _create_request(db_session, student.student_id, confirmed=True)
        _create_request(db_session, student.student_id, confirmed=False)

        results = RequestService.get_student_requests(db_session, student.student_id)
        assert len(results) == 2

    def test_status_filter_works(self, db_session):
        """
        TEST CASE: When status filter is applied, only matching requests
        are returned.
        WHY: The student requests page has filter tabs (All/Pending/Approved/
        Rejected). The backend must correctly filter by status.
        """
        student = _create_student(db_session)
        _create_request(db_session, student.student_id, status=RequestStatus.PENDING)
        _create_request(db_session, student.student_id, status=RequestStatus.APPROVED)
        _create_request(db_session, student.student_id, status=RequestStatus.REJECTED)

        approved = RequestService.get_student_requests(db_session, student.student_id, status="approved")
        assert len(approved) == 1
        assert approved[0]["status"] == RequestStatus.APPROVED

    def test_invalid_status_is_ignored(self, db_session):
        """
        TEST CASE: An invalid status string in the filter should not crash
        — instead, all requests are returned.
        WHY: Defensive handling of bad input prevents the requests page
        from crashing if the frontend ever sends a typo.
        """
        student = _create_student(db_session)
        _create_request(db_session, student.student_id)
        _create_request(db_session, student.student_id)

        # Invalid status — should fall through silently and return all
        results = RequestService.get_student_requests(db_session, student.student_id, status="bogus")
        assert len(results) == 2


class TestGetAllRequests:
    """Tests for admin retrieval of all requests."""

    def test_only_confirmed_requests_returned(self, db_session):
        """
        TEST CASE: Admin view must only show confirmed requests.
        WHY: Unconfirmed requests are drafts that the student is still
        editing. They should never appear in admin's queue until the
        student explicitly submits them for review.
        """
        student = _create_student(db_session)
        _create_request(db_session, student.student_id, confirmed=True)
        _create_request(db_session, student.student_id, confirmed=True)
        _create_request(db_session, student.student_id, confirmed=False)

        results = RequestService.get_all_requests(db_session)
        assert len(results) == 2
        for r in results:
            assert r["confirmed"] is True

    def test_status_filter_works(self, db_session):
        """
        TEST CASE: The admin view supports status filtering.
        WHY: Admin needs to filter by pending/approved/rejected to manage
        their workload. This is the same filter pattern as the student view.
        """
        student = _create_student(db_session)
        _create_request(db_session, student.student_id, status=RequestStatus.PENDING)
        _create_request(db_session, student.student_id, status=RequestStatus.APPROVED)

        pending = RequestService.get_all_requests(db_session, status="pending")
        assert len(pending) == 1
        assert pending[0]["status"] == RequestStatus.PENDING

    def test_timeframe_filter_today(self, db_session):
        """
        TEST CASE: The 'today' timeframe must only return requests submitted
        in the last 24 hours.
        WHY: Time-based filtering is used by admin to view recent submissions
        without scrolling through old data.
        """
        student = _create_student(db_session)
        # Recent request
        _create_request(
            db_session, student.student_id,
            submit_timestamp=datetime.utcnow() - timedelta(hours=2)
        )
        # Old request
        _create_request(
            db_session, student.student_id,
            submit_timestamp=datetime.utcnow() - timedelta(days=5)
        )

        results = RequestService.get_all_requests(db_session, timeframe="today")
        assert len(results) == 1

    def test_no_timeframe_returns_all(self, db_session):
        """
        TEST CASE: When no timeframe is given, requests from any date are returned.
        WHY: The 'All time' filter option should not apply any time restriction.
        """
        student = _create_student(db_session)
        _create_request(
            db_session, student.student_id,
            submit_timestamp=datetime.utcnow() - timedelta(days=365)
        )
        _create_request(db_session, student.student_id)

        results = RequestService.get_all_requests(db_session)
        assert len(results) == 2

    def test_includes_fraud_details(self, db_session):
        """
        TEST CASE: Admin view must include the full risk assessment data
        for each receipt.
        WHY: Admins need to see fraud layer breakdowns to make informed
        approval decisions. Without this, the fraud detection panel is empty.
        """
        student = _create_student(db_session)
        request = _create_request(db_session, student.student_id)
        _create_receipt_with_risk(
            db_session, request.request_id, student.student_id,
            total_risk=0.7, assessment="high_risk"
        )

        results = RequestService.get_all_requests(db_session)
        assert len(results) == 1
        assert results[0]["receipts"][0]["risk_assessment"]["assessment"] == "high_risk"


class TestDecideRequest:
    """Tests for the admin approve/reject decision."""

    def test_approve_sets_status_and_timestamp(self, db_session):
        """
        TEST CASE: Approving a request must set status to APPROVED and
        record the review_timestamp.
        WHY: This is the core admin action. Status change determines
        whether the student gets reimbursed. Timestamp provides audit trail.
        """
        student = _create_student(db_session)
        request = _create_request(db_session, student.student_id)

        result = RequestService.decide_request(
            db_session, request.request_id, decision="approve", feedback="LGTM"
        )
        assert "error" not in result
        assert result["status"] == RequestStatus.APPROVED
        assert result["admin_feedback"] == "LGTM"
        assert result["review_timestamp"] is not None

    def test_reject_sets_status_and_feedback(self, db_session):
        """
        TEST CASE: Rejecting a request must set status to REJECTED and
        save the admin's feedback message.
        WHY: Feedback explains the rejection to the student. Without it,
        students wouldn't know why their request was denied.
        """
        student = _create_student(db_session)
        request = _create_request(db_session, student.student_id)

        result = RequestService.decide_request(
            db_session, request.request_id, decision="reject", feedback="STPT ID mismatch"
        )
        assert result["status"] == RequestStatus.REJECTED
        assert result["admin_feedback"] == "STPT ID mismatch"

    def test_cannot_decide_already_decided_request(self, db_session):
        """
        TEST CASE: Once a request is approved or rejected, further decision
        attempts must be rejected.
        WHY: Decisions should be final — re-deciding could create audit
        confusion and inconsistent reimbursement records.
        """
        student = _create_student(db_session)
        request = _create_request(db_session, student.student_id, status=RequestStatus.APPROVED)

        result = RequestService.decide_request(
            db_session, request.request_id, decision="reject"
        )
        assert "error" in result
        assert "already decided" in result["error"].lower()

    def test_invalid_decision_returns_error(self, db_session):
        """
        TEST CASE: Decision strings other than 'approve' or 'reject' must
        return an error.
        WHY: Defensive input validation — the frontend should only ever
        send these two values, but the backend must guard against bad input.
        """
        student = _create_student(db_session)
        request = _create_request(db_session, student.student_id)

        result = RequestService.decide_request(
            db_session, request.request_id, decision="maybe"
        )
        assert "error" in result

    def test_nonexistent_request_returns_error(self, db_session):
        """
        TEST CASE: Trying to decide a request_id that doesn't exist
        must return an error.
        WHY: Defensive handling of bad input — URL tampering or stale
        frontend state should not crash the backend.
        """
        result = RequestService.decide_request(
            db_session, 99999, decision="approve"
        )
        assert "error" in result
        assert "not found" in result["error"].lower()