# app/services/metadata_service.py
from sqlalchemy.orm import Session
from ..database.models.receipt_metadata import ReceiptMetadata
from typing import Dict

class MetadataService:
    """Service to save fraud detection results to database"""
    
    @staticmethod
    def save_layer2_results(db: Session, receipt_id: str, layer2_analysis: Dict) -> ReceiptMetadata:
        """
        Save Layer 2 EXIF analysis results to database
        Creates or updates ReceiptMetadata entry
        """
        # Check if metadata already exists for this receipt
        metadata = db.query(ReceiptMetadata).filter(
            ReceiptMetadata.receipt_id == receipt_id
        ).first()
        
        if not metadata:
            # Create new metadata entry
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
        metadata.assessment = layer2_analysis.get("assessment")
        
        # Initial tampering score (will be updated when all layers complete)
        metadata.tampering_score = layer2_analysis.get("risk_score", 0.0)
        
        db.commit()
        db.refresh(metadata)
        
        return metadata
    
    @staticmethod
    def update_combined_risk_score(
        db: Session, 
        receipt_id: str,
        layer1_fraud: bool = False,
        layer1_duplicate: bool = False
    ) -> ReceiptMetadata:
        """
        Update combined risk score based on all layers
        """
        metadata = db.query(ReceiptMetadata).filter(
            ReceiptMetadata.receipt_id == receipt_id
        ).first()
        
        if not metadata:
            return None
        
        # Start with Layer 2 risk
        total_risk = metadata.layer2_risk_score or 0.0
        
        # Add Layer 1 risks
        if layer1_fraud:
            total_risk += 0.9  # Almost certain fraud
        elif layer1_duplicate:
            total_risk += 0.3
        
        # Add Layer 3 risk (when implemented)
        total_risk += metadata.layer3_risk_score or 0.0
        
        # Add Layer 4 risk (when implemented)
        total_risk += metadata.layer4_risk_score or 0.0
        
        # Cap at 1.0
        total_risk = min(total_risk, 1.0)
        
        # Update assessment
        if total_risk >= 0.7:
            assessment = "high_risk"
        elif total_risk >= 0.4:
            assessment = "medium_risk"
        else:
            assessment = "low_risk"
        
        metadata.tampering_score = total_risk
        metadata.assessment = assessment
        
        # Build detailed risk factors
        risk_factors = {
            "layer1": {
                "fraud_detected": layer1_fraud,
                "duplicate_detected": layer1_duplicate
            },
            "layer2": {
                "risk_score": metadata.layer2_risk_score,
                "flags": metadata.exif_flags,
                "has_editing_software": metadata.has_editing_software,
                "editing_software": metadata.editing_software_name
            },
            "total_risk": total_risk,
            "assessment": assessment
        }
        
        metadata.risk_factors = risk_factors
        
        db.commit()
        db.refresh(metadata)
        
        return metadata
    
    @staticmethod
    def get_metadata(db: Session, receipt_id: str) -> ReceiptMetadata:
        """Retrieve metadata for a receipt"""
        return db.query(ReceiptMetadata).filter(
            ReceiptMetadata.receipt_id == receipt_id
        ).first()