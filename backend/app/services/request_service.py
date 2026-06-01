# app/services/request_service.py
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from ..database.models.request import Request, RequestStatus
from ..database.models.receipt import Receipt
from ..database.models.receipt_risk_assessment import ReceiptRiskAssessment
from ..database.models.student import Student


class RequestService:

    @staticmethod
    def _format_request(request: Request, include_fraud_details: bool = False) -> dict:
        receipts = []
        for receipt in request.receipts:
            r = {
                "receipt_id": receipt.receipt_id,
                "file_path": receipt.file_path,
                "sha256_hash": receipt.sha256_hash,
            }
            if include_fraud_details and receipt.risk_assessment:
                ra = receipt.risk_assessment
                r["risk_assessment"] = {
                    "total_risk_score": ra.total_risk_score,
                    "assessment": ra.assessment,
                    "layer1_risk": ra.layer1_risk,
                    "layer2_risk": ra.layer2_risk,
                    "layer3_risk": ra.layer3_risk,
                    "layer4_risk": ra.layer4_risk,
                    "risk_factors": ra.risk_factors,
                }
            receipts.append(r)

        return {
            "request_id": request.request_id,
            "student_id": request.student_id,
            "status": request.status,
            "comment": request.comment,
            "admin_feedback": request.admin_feedback,
            "submit_timestamp": request.submit_timestamp,
            "review_timestamp": request.review_timestamp,
            "confirmed": request.confirmed,
            "resubmission_count": request.resubmission_count,
            "last_resubmit_timestamp": request.last_resubmit_timestamp,
            "receipts": receipts,
        }

    @staticmethod
    def _apply_timeframe_filter(query, timeframe: Optional[str]):
        if not timeframe:
            return query
        now = datetime.utcnow()
        timeframe_map = {
            "today":      now - timedelta(days=1),
            "this_week":  now - timedelta(weeks=1),
            "this_month": now - timedelta(days=30),
            "3_months":   now - timedelta(days=90),
            "6_months":   now - timedelta(days=180),
            "this_year":  now - timedelta(days=365),
        }
        cutoff = timeframe_map.get(timeframe)
        if cutoff:
            query = query.filter(Request.submit_timestamp >= cutoff)
        return query

    @staticmethod
    def get_student_requests(
        db: Session,
        student_id: int,
        status: Optional[str] = None
    ) -> list:
        query = db.query(Request).filter(Request.student_id == student_id)
        if status:
            try:
                query = query.filter(Request.status == RequestStatus(status))
            except ValueError:
                pass
        requests = query.order_by(Request.submit_timestamp.desc()).all()
        return [RequestService._format_request(r) for r in requests]

    @staticmethod
    def get_all_requests(
        db: Session,
        status: Optional[str] = None,
        timeframe: Optional[str] = None
    ) -> list:
        """Only returns confirmed requests — student has reviewed and submitted."""
        query = db.query(Request).filter(Request.confirmed == True)

        if status:
            try:
                query = query.filter(Request.status == RequestStatus(status))
            except ValueError:
                pass

        query = RequestService._apply_timeframe_filter(query, timeframe)
        requests = query.order_by(Request.submit_timestamp.desc()).all()
        return [RequestService._format_request(r, include_fraud_details=True) for r in requests]

    @staticmethod
    def decide_request(
        db: Session,
        request_id: int,
        decision: str,
        feedback: Optional[str] = None
    ) -> dict:
        request = db.query(Request).filter(Request.request_id == request_id).first()
        if not request:
            return {"error": "Request not found"}

        if request.status not in [RequestStatus.PENDING]:
            return {"error": f"Request already decided (status: {request.status})"}

        if decision == "approve":
            request.status = RequestStatus.APPROVED
        elif decision == "reject":
            request.status = RequestStatus.REJECTED
        else:
            return {"error": "Decision must be 'approve' or 'reject'"}

        request.review_timestamp = datetime.utcnow()
        request.admin_feedback = feedback

        db.commit()
        db.refresh(request)

        return RequestService._format_request(request, include_fraud_details=True)
