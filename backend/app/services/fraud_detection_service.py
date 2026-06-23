# app/services/fraud_detection_service.py
from sqlalchemy.orm import Session
from ..database.models.receipt_metadata import ReceiptMetadata
from ..database.models.receipt_ocr import ReceiptOCR
from ..database.models.receipt_anomalies import ReceiptAnomalies
from ..database.models.receipt_risk_assessment import ReceiptRiskAssessment
from ..database.models.student import Student
from typing import Dict
import json


# Weights for the weighted sum risk aggregation (Layer 5)
# Must sum to 1.0
LAYER_WEIGHTS = {
    "layer1": 0.30,  # Hash — exact duplicate is a strong fraud signal
    "layer2": 0.25,  # EXIF — metadata anomalies are indicative but not definitive
    "layer3": 0.20,  # OCR — STPT ID mismatch is a strong fraud signal
    "layer4": 0.25,  # Anomaly — pattern analysis is supportive but less definitive
}


class FraudDetectionService:
    """Service to save fraud detection results to database"""

    @staticmethod
    def save_layer2_results(db: Session, receipt_id: str, layer2_analysis: Dict) -> ReceiptMetadata:
        """Save Layer 2 EXIF analysis results to receipt_metadata table"""
        metadata = db.query(ReceiptMetadata).filter(
            ReceiptMetadata.receipt_id == receipt_id
        ).first()

        if not metadata:
            metadata = ReceiptMetadata(receipt_id=receipt_id)
            db.add(metadata)

        metadata.exif_status = layer2_analysis.get("exif_status")
        metadata.has_editing_software = layer2_analysis.get("has_editing_software", False)
        metadata.editing_software_name = layer2_analysis.get("editing_software")
        metadata.is_mobile_camera = layer2_analysis.get("is_mobile_camera")
        metadata.camera_model = layer2_analysis.get("camera_model")
        metadata.photo_age_days = layer2_analysis.get("photo_age_days")
        metadata.has_exif_inconsistencies = layer2_analysis.get("has_inconsistencies", False)
        metadata.exif_flags = layer2_analysis.get("flags", [])
        metadata.layer2_risk_score = layer2_analysis.get("risk_score", 0.0)

        db.commit()
        db.refresh(metadata)
        return metadata

    @staticmethod
    def save_layer3_results(
        db: Session,
        receipt_id: str,
        student_id: int,
        ocr_result: Dict,
        ocr_engine: str = "consensus"
    ) -> ReceiptOCR:
        """Save Layer 3 OCR analysis results to receipt_ocr table"""
        student = db.query(Student).filter(Student.student_id == student_id).first()
        expected_stpt_id = student.stpt_id if student else None
        extracted_stpt_id = ocr_result.get("stpt_id")

        stpt_matches = False
        if extracted_stpt_id and expected_stpt_id:

            # Substring check handles leading zeros that vary between card and receipt
            stpt_matches = (
                extracted_stpt_id == expected_stpt_id or
                extracted_stpt_id in expected_stpt_id
            )

        layer3_risk = 0.0
        ocr_flags = []

        if not extracted_stpt_id:
            layer3_risk += 0.4
            ocr_flags.append("stpt_id_not_found")
        elif not stpt_matches:
            layer3_risk += 0.9
            ocr_flags.append("stpt_id_mismatch")

        if ocr_result.get("stpt_id_confidence", 0) < 0.7:
            layer3_risk += 0.2
            ocr_flags.append("low_ocr_confidence")

        ocr_data = db.query(ReceiptOCR).filter(
            ReceiptOCR.receipt_id == receipt_id
        ).first()

        if not ocr_data:
            ocr_data = ReceiptOCR(receipt_id=receipt_id)
            db.add(ocr_data)

        ocr_data.ocr_engine_used = ocr_engine
        ocr_data.extracted_receipt_id = ocr_result.get("receipt_id")
        ocr_data.extracted_stpt_id = extracted_stpt_id
        ocr_data.expected_stpt_id = expected_stpt_id
        ocr_data.stpt_id_matches_student = stpt_matches
        ocr_data.ocr_confidence = ocr_result.get("average_confidence", 0.0)
        ocr_data.stpt_id_confidence = ocr_result.get("stpt_id_confidence", 0.0)
        ocr_data.receipt_id_confidence = ocr_result.get("receipt_id_confidence", 0.0)
        ocr_data.raw_ocr_text = ocr_result.get("raw_text", "")[:1000]
        ocr_data.layer3_risk_score = min(layer3_risk, 1.0)
        ocr_data.ocr_flags = json.dumps(ocr_flags)

        db.commit()
        db.refresh(ocr_data)
        return ocr_data

    @staticmethod
    def save_layer4_results(
        db: Session,
        receipt_id: str,
        layer4_analysis: Dict
    ) -> ReceiptAnomalies:
        """Save Layer 4 anomaly detection results to receipt_anomalies table."""
        anomaly_data = db.query(ReceiptAnomalies).filter(
            ReceiptAnomalies.receipt_id == receipt_id
        ).first()

        if not anomaly_data:
            anomaly_data = ReceiptAnomalies(receipt_id=receipt_id)
            db.add(anomaly_data)

        anomaly_data.receipt_id_length_anomaly = layer4_analysis.get("length_anomaly", False)
        anomaly_data.prefix_rarity_score = layer4_analysis.get("prefix_rarity_score", 0.0)
        anomaly_data.digram_rarity_score = layer4_analysis.get("digram_rarity_score", 0.0)
        anomaly_data.layer4_risk_score = layer4_analysis.get("layer4_risk_score", 0.0)

        # Write extracted receipt ID back to receipt_ocr, Layer 3 leaves it as None for now since Layer 4 is where it actually gets extracted
        extracted_receipt_id = layer4_analysis.get("extracted_receipt_id")
        if extracted_receipt_id:
            ocr_record = db.query(ReceiptOCR).filter(
                ReceiptOCR.receipt_id == receipt_id
            ).first()
            if ocr_record:
                ocr_record.extracted_receipt_id = extracted_receipt_id

        db.commit()
        db.refresh(anomaly_data)
        return anomaly_data

    @staticmethod
    def update_final_risk_assessment(
        db: Session,
        receipt_id: str,
        layer1_fraud: bool = False,
        layer1_duplicate: bool = False,
        layer4_risk: float = 0.0
    ) -> ReceiptRiskAssessment:
        """
        Calculate and save final risk assessment (Layer 5).
        Weights are defined in LAYER_WEIGHTS and reflect the relative
        importance of each layer's signal.
        """
        exif_data = db.query(ReceiptMetadata).filter(
            ReceiptMetadata.receipt_id == receipt_id
        ).first()

        ocr_data = db.query(ReceiptOCR).filter(
            ReceiptOCR.receipt_id == receipt_id
        ).first()

        # Layer 1 risk
        layer1_risk = 0.0
        if layer1_fraud:
            layer1_risk = 0.9
        elif layer1_duplicate:
            layer1_risk = 0.3

        layer2_risk = exif_data.layer2_risk_score if exif_data else 0.0
        layer3_risk = ocr_data.layer3_risk_score if ocr_data else 0.0
        layer4_risk = min(layer4_risk, 1.0)

        # Weighted sum: R = w1*H + w2*E + w3*O + w4*A
        total_risk = (
            LAYER_WEIGHTS["layer1"] * layer1_risk +
            LAYER_WEIGHTS["layer2"] * layer2_risk +
            LAYER_WEIGHTS["layer3"] * layer3_risk +
            LAYER_WEIGHTS["layer4"] * layer4_risk
        )
        total_risk = min(round(total_risk, 4), 1.0)

                # Critical signal overrides. Can be altered according to need and observation.
        if layer1_fraud:
            total_risk = max(total_risk, 0.9)   # exact file submitted by another student
        if layer2_risk >= 0.7:
            total_risk = max(total_risk, 0.75)  # no EXIF or editing software detected
        if layer3_risk >= 0.4:
            total_risk = max(total_risk, 0.75)  # any STPT ID failure, not found or mismatch
        if layer4_risk >= 0.8:
            total_risk = max(total_risk, 0.75)  # solo pattern or exact duplicate receipt ID

        total_risk = min(round(total_risk, 4), 1.0)

        if total_risk >= 0.7:
            assessment = "high_risk"
        elif total_risk >= 0.4:
            assessment = "medium_risk"
        else:
            assessment = "low_risk"

        risk_factors = {
            "layer1_hash": {
                "fraud_detected": layer1_fraud,
                "duplicate_detected": layer1_duplicate,
                "risk": layer1_risk,
                "weight": LAYER_WEIGHTS["layer1"]
            },
            "layer2_exif": {
                "has_editing_software": exif_data.has_editing_software if exif_data else False,
                "editing_software": exif_data.editing_software_name if exif_data else None,
                "flags": exif_data.exif_flags if exif_data else [],
                "risk": layer2_risk,
                "weight": LAYER_WEIGHTS["layer2"]
            },
            "layer3_ocr": {
                "stpt_id_matches": ocr_data.stpt_id_matches_student if ocr_data else None,
                "extracted_stpt_id": ocr_data.extracted_stpt_id if ocr_data else None,
                "expected_stpt_id": ocr_data.expected_stpt_id if ocr_data else None,
                "flags": json.loads(ocr_data.ocr_flags) if ocr_data and isinstance(ocr_data.ocr_flags, str) else (ocr_data.ocr_flags if ocr_data else []),
                "risk": layer3_risk,
                "weight": LAYER_WEIGHTS["layer3"]
            },
            "layer4_anomaly": {
                "risk": layer4_risk,
                "weight": LAYER_WEIGHTS["layer4"]
            },
            "total_risk": total_risk,
            "assessment": assessment
        }

        risk_assessment = db.query(ReceiptRiskAssessment).filter(
            ReceiptRiskAssessment.receipt_id == receipt_id
        ).first()

        if not risk_assessment:
            risk_assessment = ReceiptRiskAssessment(receipt_id=receipt_id)
            db.add(risk_assessment)

        risk_assessment.total_risk_score = total_risk
        risk_assessment.assessment = assessment
        risk_assessment.risk_factors = risk_factors
        risk_assessment.layer1_risk = layer1_risk
        risk_assessment.layer2_risk = layer2_risk
        risk_assessment.layer3_risk = layer3_risk
        risk_assessment.layer4_risk = layer4_risk

        db.commit()
        db.refresh(risk_assessment)
        return risk_assessment
