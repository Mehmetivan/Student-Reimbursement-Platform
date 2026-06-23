# app/services/validation/anomaly_service.py
from sqlalchemy.orm import Session
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import re
import logging

from ...database.models.receipt_anomalies import ReceiptAnomalies
from ...database.models.receipt_ocr import ReceiptOCR
from ...database.models.receipt_metadata import ReceiptMetadata
from ...database.models.receipt_risk_assessment import ReceiptRiskAssessment

logger = logging.getLogger(__name__)

LAYER_WEIGHTS = {
    "layer1": 0.35,
    "layer2": 0.20,
    "layer3": 0.35,
    "layer4": 0.10,
}


def _recalculate_final_risk(db: Session, receipt_id: str, new_layer4_risk: float) -> None:
    """
    Recalculate and update receipt_risk_assessment when Layer 4 risk changes.
    Uses the same weighted sum + override logic as fraud_detection_service.py.
    """
    exif_data = db.query(ReceiptMetadata).filter(ReceiptMetadata.receipt_id == receipt_id).first()
    ocr_data = db.query(ReceiptOCR).filter(ReceiptOCR.receipt_id == receipt_id).first()
    risk_assessment = db.query(ReceiptRiskAssessment).filter(ReceiptRiskAssessment.receipt_id == receipt_id).first()

    if not risk_assessment:
        return

    layer1_risk = risk_assessment.layer1_risk or 0.0
    layer2_risk = exif_data.layer2_risk_score if exif_data else 0.0
    layer3_risk = ocr_data.layer3_risk_score if ocr_data else 0.0
    layer4_risk = min(new_layer4_risk, 1.0)

    total_risk = (
        LAYER_WEIGHTS["layer1"] * layer1_risk +
        LAYER_WEIGHTS["layer2"] * layer2_risk +
        LAYER_WEIGHTS["layer3"] * layer3_risk +
        LAYER_WEIGHTS["layer4"] * layer4_risk
    )
    total_risk = min(round(total_risk, 4), 1.0)

    if layer1_risk >= 0.9:
        total_risk = max(total_risk, 0.9)
    if layer2_risk >= 0.7:
        total_risk = max(total_risk, 0.75)
    if layer3_risk >= 0.4:
        total_risk = max(total_risk, 0.75)
    if layer4_risk >= 0.8:
        total_risk = max(total_risk, 0.75)

    total_risk = min(round(total_risk, 4), 1.0)

    if total_risk >= 0.7:
        assessment = "high_risk"
    elif total_risk >= 0.4:
        assessment = "medium_risk"
    else:
        assessment = "low_risk"

    risk_assessment.layer4_risk = layer4_risk
    risk_assessment.total_risk_score = total_risk
    risk_assessment.assessment = assessment

    if risk_assessment.risk_factors:
        factors = dict(risk_assessment.risk_factors)
        if "layer4_anomaly" in factors:
            factors["layer4_anomaly"]["risk"] = layer4_risk
        factors["total_risk"] = total_risk
        factors["assessment"] = assessment
        risk_assessment.risk_factors = factors

    logger.info(f" Updated risk_assessment for {receipt_id[:8]}...: total={total_risk}, assessment={assessment}")


class AnomalyService:
    """Layer 4: Receipt ID Structural Anomaly Detection"""

    SLIDING_WINDOW_DAYS = 90
    MIN_CLUSTER_SIZE = 3

    RISK_SCORES = {
        "duplicate": 1.0,
        "solo": 0.8,
        "pair": 0.6,
        "triplet": 0.4,
        "cluster": 0.2
    }

    @staticmethod
    def extract_receipt_id_from_ocr(easyocr_text: str, google_vision_text: str) -> Tuple[Optional[str], float]:
        pattern = r'(\d{3,4})-(\d{5,6})-(\d{6,7})'
        easyocr_match = re.search(pattern, easyocr_text)
        google_match = re.search(pattern, google_vision_text)
        easyocr_id = easyocr_match.group(0) if easyocr_match else None
        google_id = google_match.group(0) if google_match else None

        if easyocr_id and google_id:
            if easyocr_id == google_id:
                return easyocr_id, 0.95
            else:
                logger.warning(f"OCR mismatch: EasyOCR={easyocr_id}, Google={google_id}")
                return google_id, 0.6
        elif google_id:
            return google_id, 0.7
        elif easyocr_id:
            return easyocr_id, 0.55
        else:
            return None, 0.0

    @staticmethod
    def analyze_structure(receipt_id: str) -> Dict:
        pattern = r'(\d{3,4})-(\d{5,6})-(\d{6,7})'
        match = re.match(pattern, receipt_id)
        if not match:
            return {"valid_format": False, "receipt_id": receipt_id}
        prefix, middle, last = match.groups()
        structure = f"{len(prefix)}-{len(middle)}-{len(last)}"
        all_digits = prefix + middle + last
        digrams = [all_digits[i:i+2] for i in range(len(all_digits) - 1)]
        stand_indicator = prefix[:2]
        return {
            "valid_format": True,
            "receipt_id": receipt_id,
            "total_length": len(receipt_id),
            "prefix": prefix,
            "middle": middle,
            "last": last,
            "structure_pattern": structure,
            "digit_count": len(all_digits),
            "digrams": digrams,
            "stand_indicator": stand_indicator,
            "all_digits": all_digits
        }

    @staticmethod
    def check_duplicate(db: Session, receipt_id_value: str, current_receipt_uuid: str = None) -> Tuple[bool, Optional[str]]:
        query = db.query(ReceiptOCR).filter(ReceiptOCR.extracted_receipt_id == receipt_id_value)
        if current_receipt_uuid:
            query = query.filter(ReceiptOCR.receipt_id != current_receipt_uuid)
        existing = query.first()
        if existing:
            logger.warning(f" DUPLICATE: {receipt_id_value} already submitted by {existing.receipt_id}!")
            return True, existing.receipt_id
        return False, None

    @staticmethod
    def find_similar_patterns(db: Session, structure: Dict, exclude_receipt_id: Optional[str] = None) -> List[Dict]:
        cutoff_date = datetime.utcnow() - timedelta(days=AnomalyService.SLIDING_WINDOW_DAYS)
        recent_receipts = db.query(ReceiptOCR).filter(ReceiptOCR.created_at >= cutoff_date).all()
        similar_receipts = []
        target_digrams = set(structure["digrams"])

        for receipt in recent_receipts:
            if exclude_receipt_id and receipt.receipt_id == exclude_receipt_id:
                continue
            if not receipt.extracted_receipt_id:
                continue
            other_structure = AnomalyService.analyze_structure(receipt.extracted_receipt_id)
            if not other_structure["valid_format"]:
                continue
            same_structure = structure["structure_pattern"] == other_structure["structure_pattern"]
            same_stand = structure["stand_indicator"] == other_structure["stand_indicator"]
            other_digrams = set(other_structure["digrams"])
            common_digrams = target_digrams.intersection(other_digrams)
            overlap_ratio = len(common_digrams) / len(target_digrams) if target_digrams else 0
            is_similar = (same_structure and same_stand) or (overlap_ratio >= 0.6)
            if is_similar:
                similar_receipts.append({
                    "receipt_id": receipt.receipt_id,
                    "extracted_receipt_id": receipt.extracted_receipt_id,
                    "structure": other_structure["structure_pattern"],
                    "stand_indicator": other_structure["stand_indicator"],
                    "digram_overlap": overlap_ratio,
                    "created_at": receipt.created_at
                })

        logger.info(f"Found {len(similar_receipts)} similar receipts in last {AnomalyService.SLIDING_WINDOW_DAYS} days")
        return similar_receipts

    @staticmethod
    def calculate_risk_score(is_duplicate: bool, similar_count: int, structure: Dict) -> Tuple[float, Dict]:
        if is_duplicate:
            risk_score = AnomalyService.RISK_SCORES["duplicate"]
            assessment = "duplicate_fraud"
        elif similar_count == 0:
            risk_score = AnomalyService.RISK_SCORES["solo"]
            assessment = "solo_pattern"
        elif similar_count == 1:
            risk_score = AnomalyService.RISK_SCORES["pair"]
            assessment = "pair_pattern"
        elif similar_count == 2:
            risk_score = AnomalyService.RISK_SCORES["triplet"]
            assessment = "triplet_pattern"
        else:
            risk_score = AnomalyService.RISK_SCORES["cluster"]
            assessment = "validated_cluster"

        anomalies = {
            "length_anomaly": structure["total_length"] not in [16, 17, 18],
            "prefix_rarity_score": AnomalyService._calculate_prefix_rarity(similar_count),
            "digram_rarity_score": AnomalyService._calculate_digram_rarity(similar_count)
        }
        return risk_score, {"assessment": assessment, "similar_pattern_count": similar_count, "is_duplicate": is_duplicate, **anomalies}

    @staticmethod
    def _calculate_prefix_rarity(similar_count: int) -> float:
        if similar_count == 0: return 1.0
        elif similar_count <= 2: return 0.7
        elif similar_count <= 5: return 0.4
        else: return 0.1

    @staticmethod
    def _calculate_digram_rarity(similar_count: int) -> float:
        if similar_count == 0: return 1.0
        elif similar_count <= 2: return 0.6
        elif similar_count <= 5: return 0.3
        else: return 0.1

    @staticmethod
    def save_anomaly_analysis(db: Session, receipt_id: str, structure: Dict, risk_score: float, analysis: Dict) -> ReceiptAnomalies:
        anomaly_record = ReceiptAnomalies(
            receipt_id=receipt_id,
            receipt_id_length_anomaly=analysis["length_anomaly"],
            prefix_rarity_score=analysis["prefix_rarity_score"],
            digram_rarity_score=analysis["digram_rarity_score"],
            layer4_risk_score=risk_score
        )
        db.add(anomaly_record)
        db.commit()
        db.refresh(anomaly_record)
        logger.info(f"✓ Saved Layer 4 for {receipt_id}: risk={risk_score}")
        return anomaly_record

    @staticmethod
    def retroactive_risk_update(db: Session, similar_receipts: List[Dict]):
        """
        Reduce risk of older receipts when a new receipt validates the pattern.
        Updates both receipt_anomalies AND receipt_risk_assessment.

        cluster_size = len(similar_receipts) + 1
        +1 accounts for the current receipt being processed which is confirmed
        similar but not yet saved to receipt_ocr.
        """
        cluster_size = len(similar_receipts) + 1

        if cluster_size < 2:
            return

        if cluster_size == 2:
            new_risk = AnomalyService.RISK_SCORES["pair"]
        elif cluster_size == 3:
            new_risk = AnomalyService.RISK_SCORES["triplet"]
        else:
            new_risk = AnomalyService.RISK_SCORES["cluster"]

        updated_count = 0
        for similar in similar_receipts:
            anomaly_record = db.query(ReceiptAnomalies).filter(
                ReceiptAnomalies.receipt_id == similar["receipt_id"]
            ).first()

            if anomaly_record and anomaly_record.layer4_risk_score > new_risk:
                old_risk = anomaly_record.layer4_risk_score
                anomaly_record.layer4_risk_score = new_risk
                anomaly_record.prefix_rarity_score = AnomalyService._calculate_prefix_rarity(cluster_size - 1)
                anomaly_record.digram_rarity_score = AnomalyService._calculate_digram_rarity(cluster_size - 1)
                updated_count += 1
                logger.info(f" Updated anomaly {similar['receipt_id'][:8]}...: {old_risk:.2f} → {new_risk:.2f}")

                # Also update the final risk assessment for this receipt
                _recalculate_final_risk(db, similar["receipt_id"], new_risk)

        if updated_count > 0:
            db.commit()
            logger.info(f"✓ Retroactively updated {updated_count} receipts in cluster")

    @staticmethod
    def analyze_receipt_id(db: Session, receipt_id: str, easyocr_text: str, google_vision_text: str) -> Dict:
        logger.info(f"Starting Layer 4 analysis for receipt {receipt_id}")

        extracted_id, ocr_confidence = AnomalyService.extract_receipt_id_from_ocr(easyocr_text, google_vision_text)
        if not extracted_id:
            return {"success": False, "error": "Could not extract receipt ID from OCR", "layer4_risk_score": 0.9, "assessment": "no_receipt_id_found"}

        structure = AnomalyService.analyze_structure(extracted_id)
        if not structure["valid_format"]:
            return {"success": False, "error": "Receipt ID format invalid", "extracted_receipt_id": extracted_id, "layer4_risk_score": 0.85, "assessment": "invalid_format"}

        is_duplicate, original_receipt_id = AnomalyService.check_duplicate(db, extracted_id, receipt_id)
        similar_receipts = AnomalyService.find_similar_patterns(db, structure, exclude_receipt_id=receipt_id)
        risk_score, analysis = AnomalyService.calculate_risk_score(is_duplicate, len(similar_receipts), structure)
        AnomalyService.save_anomaly_analysis(db, receipt_id, structure, risk_score, analysis)

        if not is_duplicate and len(similar_receipts) >= 1:
            AnomalyService.retroactive_risk_update(db, similar_receipts)

        return {
            "success": True,
            "extracted_receipt_id": extracted_id,
            "ocr_confidence": ocr_confidence,
            "structure": structure["structure_pattern"],
            "is_duplicate": is_duplicate,
            "original_receipt_id": original_receipt_id if is_duplicate else None,
            "similar_pattern_count": len(similar_receipts),
            "layer4_risk_score": risk_score,
            "assessment": analysis["assessment"],
            "length_anomaly": analysis["length_anomaly"],
            "prefix_rarity_score": analysis["prefix_rarity_score"],
            "digram_rarity_score": analysis["digram_rarity_score"]
        }

    @staticmethod
    def _get_explanation(result: Dict) -> str:
        if result.get("is_duplicate"):
            return f"This receipt ID ({result.get('extracted_receipt_id')}) has already been submitted before."
        count = result.get("similar_pattern_count", 0)
        structure = result.get("structure", "unknown")
        if count == 0:
            return f"This is the first receipt we've seen with this pattern ({structure}). Needs validation from more submissions."
        elif count == 1:
            return f"Found 1 other receipt with a similar pattern. Partially validates it, but more data needed."
        elif count == 2:
            return f"Found 2 other receipts with matching patterns. Pattern is emerging as legitimate."
        else:
            return f"Found {count} receipts with matching patterns. Pattern is well-established and validated."

    @staticmethod
    def _get_risk_explanation(assessment: str, risk: float) -> str:
        explanations = {
            "duplicate_fraud": "Exact duplicate = maximum fraud risk (1.0)",
            "solo_pattern": "No similar patterns found = high risk (0.8) - could be fabricated",
            "pair_pattern": "Only 1 similar receipt = medium-high risk (0.6) - needs more validation",
            "triplet_pattern": "2 similar receipts found = medium risk (0.4) - pattern emerging",
            "validated_cluster": "3+ similar receipts = low risk (0.2) - pattern validated"
        }
        return explanations.get(assessment, f"Risk score: {risk}")

    @staticmethod
    def _get_next_steps(assessment: str) -> str:
        if assessment == "duplicate_fraud":
            return " Automatically rejected. Contact admin if you believe this is an error."
        elif assessment == "solo_pattern":
            return " Flagged for admin review. If legitimate, future similar receipts will validate this pattern."
        elif assessment in ["pair_pattern", "triplet_pattern"]:
            return " Flagged for admin review. Pattern is emerging but not yet fully validated."
        else:
            return " Pattern validated. Receipt can be auto-approved (pending other layer checks)."
