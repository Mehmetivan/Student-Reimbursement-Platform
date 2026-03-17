# app/services/fraud_detecion_service.py
from sqlalchemy.orm import Session
from ..database.models.receipt_metadata import ReceiptMetadata
from ..database.models.receipt_ocr import ReceiptOCR
from ..database.models.receipt_risk_assessment import ReceiptRiskAssessment
from ..database.models.student import Student
from typing import Dict

class FraudDetectionService:
    """Service to save fraud detection results to database"""
    
    @staticmethod
    def save_layer2_results(db: Session, receipt_id: str, layer2_analysis: Dict) -> ReceiptMetadata:
        """
        Save Layer 2 EXIF analysis results to receipt_metadata table
        """
        # Check if metadata already exists
        metadata = db.query(ReceiptMetadata).filter(
            ReceiptMetadata.receipt_id == receipt_id
        ).first()
        
        if not metadata:
            metadata = ReceiptMetadata(receipt_id=receipt_id)
            db.add(metadata)
        
        # Update Layer 2 fields
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
        """
        Save Layer 3 OCR analysis results to receipt_ocr table
        
        Args:
            receipt_id: UUID of the receipt
            student_id: ID of the student who submitted
            ocr_result: OCR analysis result dict
            ocr_engine: Which OCR engine was used
        """
        # Get student's registered STPT ID
        student = db.query(Student).filter(Student.student_id == student_id).first()
        expected_stpt_id = student.stpt_id if student else None
        
        # Extract STPT ID from OCR
        extracted_stpt_id = ocr_result.get("stpt_id")
        
        # Validate: Does extracted STPT match student's registered STPT?
        stpt_matches = False
        if extracted_stpt_id and expected_stpt_id:
            stpt_matches = (extracted_stpt_id == expected_stpt_id)
        
        # Calculate Layer 3 risk score
        layer3_risk = 0.0
        ocr_flags = []
        
        if not extracted_stpt_id:
            layer3_risk += 0.4
            ocr_flags.append("stpt_id_not_found")
        elif not stpt_matches:
            layer3_risk += 0.9  # HIGH RISK - STPT ID mismatch = fraud!
            ocr_flags.append("stpt_id_mismatch")
        
        if ocr_result.get("stpt_id_confidence", 0) < 0.7:
            layer3_risk += 0.2
            ocr_flags.append("low_ocr_confidence")
        
        # Check if OCR record exists
        ocr_data = db.query(ReceiptOCR).filter(
            ReceiptOCR.receipt_id == receipt_id
        ).first()
        
        if not ocr_data:
            ocr_data = ReceiptOCR(receipt_id=receipt_id)
            db.add(ocr_data)
        
        # Update OCR fields
        ocr_data.ocr_engine_used = ocr_engine
        ocr_data.extracted_receipt_id = ocr_result.get("receipt_id")
        ocr_data.extracted_stpt_id = extracted_stpt_id
        ocr_data.expected_stpt_id = expected_stpt_id
        ocr_data.stpt_id_matches_student = stpt_matches
        ocr_data.ocr_confidence = ocr_result.get("average_confidence", 0.0)
        ocr_data.stpt_id_confidence = ocr_result.get("stpt_id_confidence", 0.0)
        ocr_data.receipt_id_confidence = ocr_result.get("receipt_id_confidence", 0.0)
        ocr_data.raw_ocr_text = ocr_result.get("raw_text", "")[:1000]  # Limit to 1000 chars
        ocr_data.layer3_risk_score = min(layer3_risk, 1.0)
        ocr_data.ocr_flags = str(ocr_flags)  # Convert list to string
        
        db.commit()
        db.refresh(ocr_data)
        
        return ocr_data
    
    @staticmethod
    def update_final_risk_assessment(
        db: Session,
        receipt_id: str,
        layer1_fraud: bool = False,
        layer1_duplicate: bool = False
    ) -> ReceiptRiskAssessment:
        """
        Calculate and save final risk assessment (Layer 5)
        Combines all layers into final score
        """
        # Get all layer data
        exif_data = db.query(ReceiptMetadata).filter(
            ReceiptMetadata.receipt_id == receipt_id
        ).first()
        
        ocr_data = db.query(ReceiptOCR).filter(
            ReceiptOCR.receipt_id == receipt_id
        ).first()
        
        # Calculate individual layer risks
        layer1_risk = 0.0
        if layer1_fraud:
            layer1_risk = 0.9
        elif layer1_duplicate:
            layer1_risk = 0.3
        
        layer2_risk = exif_data.layer2_risk_score if exif_data else 0.0
        layer3_risk = ocr_data.layer3_risk_score if ocr_data else 0.0
        layer4_risk = 0.0  # Not implemented yet
        
        # Calculate total risk (weighted average or max)
        total_risk = max(layer1_risk, layer2_risk, layer3_risk, layer4_risk)
        
        # Determine assessment
        if total_risk >= 0.7:
            assessment = "high_risk"
        elif total_risk >= 0.4:
            assessment = "medium_risk"
        else:
            assessment = "low_risk"
        
        # Build risk factors breakdown
        risk_factors = {
            "layer1_hash": {
                "fraud_detected": layer1_fraud,
                "duplicate_detected": layer1_duplicate,
                "risk": layer1_risk
            },
            "layer2_exif": {
                "has_editing_software": exif_data.has_editing_software if exif_data else False,
                "editing_software": exif_data.editing_software_name if exif_data else None,
                "flags": exif_data.exif_flags if exif_data else [],
                "risk": layer2_risk
            },
            "layer3_ocr": {
                "stpt_id_matches": ocr_data.stpt_id_matches_student if ocr_data else None,
                "extracted_stpt_id": ocr_data.extracted_stpt_id if ocr_data else None,
                "expected_stpt_id": ocr_data.expected_stpt_id if ocr_data else None,
                "flags": ocr_data.ocr_flags if ocr_data else [],
                "risk": layer3_risk
            },
            "total_risk": total_risk,
            "assessment": assessment
        }
        
        # Check if risk assessment exists
        risk_assessment = db.query(ReceiptRiskAssessment).filter(
            ReceiptRiskAssessment.receipt_id == receipt_id
        ).first()
        
        if not risk_assessment:
            risk_assessment = ReceiptRiskAssessment(receipt_id=receipt_id)
            db.add(risk_assessment)
        
        # Update assessment
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