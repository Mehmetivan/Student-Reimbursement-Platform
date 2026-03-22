# app/services/validation/anomaly_service.py
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime, timedelta
import re
import logging
from collections import Counter

from ...database.models.receipt_anomalies import ReceiptAnomalies
from ...database.models.receipt_ocr import ReceiptOCR
from .multi_ocr_service import MultiOCRService

logger = logging.getLogger(__name__)

class AnomalyService:
    """
    Layer 4: Receipt ID Structural Anomaly Detection
    
    Analyzes receipt ID patterns to detect:
    - Duplicate submissions (exact ID match)
    - Structural anomalies (length, prefix, digit patterns)
    - Pattern validation through clustering
    - Retroactive risk adjustment as patterns emerge
    """
    
    # Configuration
    SLIDING_WINDOW_DAYS = 90  # Compare against receipts from last 90 days
    MIN_CLUSTER_SIZE = 3      # 3+ matching receipts = validated pattern
    
    # Risk thresholds based on pattern matches
    RISK_SCORES = {
        "duplicate": 1.0,      # Exact duplicate = maximum fraud risk
        "solo": 0.8,           # 0 matching receipts = high risk
        "pair": 0.6,           # 1 matching receipt = medium-high risk
        "triplet": 0.4,        # 2 matching receipts = medium risk
        "cluster": 0.2         # 3+ matching receipts = low risk (validated)
    }
    
    @staticmethod
    def extract_receipt_id_from_ocr(
        easyocr_text: str,
        google_vision_text: str
    ) -> Tuple[Optional[str], float]:
        """
        Extract receipt ID using consensus between EasyOCR and Google Vision
        
        Format: PREFIX-MIDDLE-LAST (e.g., 324-19204-121115)
        - Prefix: 3-4 digits
        - Middle: 5-6 digits
        - Last: 6-7 digits
        
        Returns: (receipt_id, confidence)
        """
        # Receipt ID pattern: 3-4 digits, dash, 5-6 digits, dash, 6-7 digits
        pattern = r'(\d{3,4})-(\d{5,6})-(\d{6,7})'
        
        # Try extracting from both OCR results
        easyocr_match = re.search(pattern, easyocr_text)
        google_match = re.search(pattern, google_vision_text)
        
        easyocr_id = easyocr_match.group(0) if easyocr_match else None
        google_id = google_match.group(0) if google_match else None
        
        # Consensus logic
        if easyocr_id and google_id:
            if easyocr_id == google_id:
                logger.info(f"✓ Both OCR engines agree: {easyocr_id}")
                return easyocr_id, 0.95  # High confidence - both agree
            else:
                logger.warning(f"⚠ OCR mismatch: EasyOCR={easyocr_id}, Google={google_id}")
                # Use Google Vision (generally more accurate)
                return google_id, 0.7  # Medium confidence - disagreement
        elif google_id:
            logger.info(f"✓ Google Vision found: {google_id}")
            return google_id, 0.85  # Good confidence - Google only
        elif easyocr_id:
            logger.info(f"✓ EasyOCR found: {easyocr_id}")
            return easyocr_id, 0.75  # Medium confidence - EasyOCR only
        else:
            logger.warning("✗ No receipt ID found by any OCR engine")
            return None, 0.0
    
    @staticmethod
    def analyze_structure(receipt_id: str) -> Dict:
        """
        Analyze structural features of a receipt ID
        
        Extracts:
        - Total length
        - Prefix, middle, last segments
        - Structure pattern (e.g., "3-5-6")
        - All digit 2-grams
        - First 2 digits of prefix (possible stand identifier)
        """
        # Parse segments
        pattern = r'(\d{3,4})-(\d{5,6})-(\d{6,7})'
        match = re.match(pattern, receipt_id)
        
        if not match:
            return {
                "valid_format": False,
                "receipt_id": receipt_id
            }
        
        prefix, middle, last = match.groups()
        
        # Structure pattern (e.g., "3-5-6" for 324-19204-121115)
        structure = f"{len(prefix)}-{len(middle)}-{len(last)}"
        
        # Extract all digits
        all_digits = prefix + middle + last
        
        # Generate all digit 2-grams (consecutive digit pairs)
        digrams = [all_digits[i:i+2] for i in range(len(all_digits) - 1)]
        
        # First 2 digits of prefix (might indicate stand/location)
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
        """
        Check if this exact receipt ID has been submitted before
        
        Searches ALL historical receipts (no time limit)
        Excludes the current receipt being processed to avoid false positives
        
        Args:
            receipt_id_value: The extracted receipt ID (e.g., "324-19204-121115")
            current_receipt_uuid: UUID of the current receipt being processed (to exclude it)
        
        Returns: (is_duplicate, original_receipt_id)
        """
        # Query OCR table for any receipt with this exact ID
        query = db.query(ReceiptOCR).filter(
            ReceiptOCR.extracted_receipt_id == receipt_id_value
        )
        
        # Exclude the current receipt if provided
        if current_receipt_uuid:
            query = query.filter(ReceiptOCR.receipt_id != current_receipt_uuid)
        
        existing = query.first()
        
        if existing:
            logger.warning(f"🚨 DUPLICATE DETECTED: Receipt ID {receipt_id_value} already submitted by {existing.receipt_id}!")
            return True, existing.receipt_id
        
        return False, None
    
    @staticmethod
    def find_similar_patterns(
        db: Session,
        structure: Dict,
        exclude_receipt_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Find receipts with similar structural patterns within sliding window
        
        Similarity criteria:
        - Same structure pattern (e.g., both "3-5-6")
        - Same or similar prefix (same first 2 digits)
        - High 2-gram overlap (60%+ shared digit pairs)
        
        Only searches receipts from last SLIDING_WINDOW_DAYS
        """
        cutoff_date = datetime.utcnow() - timedelta(days=AnomalyService.SLIDING_WINDOW_DAYS)
        
        # Get all receipts within sliding window
        recent_receipts = db.query(ReceiptOCR).filter(
            ReceiptOCR.created_at >= cutoff_date
        ).all()
        
        similar_receipts = []
        target_digrams = set(structure["digrams"])
        
        for receipt in recent_receipts:
            # Skip if this is the same receipt we're analyzing
            if exclude_receipt_id and receipt.receipt_id == exclude_receipt_id:
                continue
            
            if not receipt.extracted_receipt_id:
                continue
            
            # Analyze this receipt's structure
            other_structure = AnomalyService.analyze_structure(receipt.extracted_receipt_id)
            
            if not other_structure["valid_format"]:
                continue
            
            # Check similarity criteria
            same_structure = (structure["structure_pattern"] == other_structure["structure_pattern"])
            same_stand = (structure["stand_indicator"] == other_structure["stand_indicator"])
            
            # Calculate 2-gram overlap
            other_digrams = set(other_structure["digrams"])
            common_digrams = target_digrams.intersection(other_digrams)
            overlap_ratio = len(common_digrams) / len(target_digrams) if target_digrams else 0
            
            # Consider similar if:
            # - Same structure AND same stand indicator
            # - OR high 2-gram overlap (60%+)
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
    def calculate_risk_score(
        is_duplicate: bool,
        similar_count: int,
        structure: Dict
    ) -> Tuple[float, Dict]:
        """
        Calculate Layer 4 risk score based on pattern analysis
        
        Risk levels:
        - Duplicate: 1.0 (maximum fraud)
        - Solo (0 matches): 0.8 (high risk)
        - Pair (1 match): 0.6 (medium-high risk)
        - Triplet (2 matches): 0.4 (medium risk)
        - Cluster (3+ matches): 0.2 (low risk, validated)
        """
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
        else:  # 3+
            risk_score = AnomalyService.RISK_SCORES["cluster"]
            assessment = "validated_cluster"
        
        # Additional anomaly flags
        anomalies = {
            "length_anomaly": structure["total_length"] not in [16, 17, 18],
            "prefix_rarity_score": AnomalyService._calculate_prefix_rarity(similar_count),
            "digram_rarity_score": AnomalyService._calculate_digram_rarity(similar_count)
        }
        
        return risk_score, {
            "assessment": assessment,
            "similar_pattern_count": similar_count,
            "is_duplicate": is_duplicate,
            **anomalies
        }
    
    @staticmethod
    def _calculate_prefix_rarity(similar_count: int) -> float:
        """
        Calculate prefix rarity score
        More similar receipts = less rare = lower score
        """
        if similar_count == 0:
            return 1.0  # Completely rare/unique
        elif similar_count <= 2:
            return 0.7  # Rare
        elif similar_count <= 5:
            return 0.4  # Uncommon
        else:
            return 0.1  # Common
    
    @staticmethod
    def _calculate_digram_rarity(similar_count: int) -> float:
        """
        Calculate digit 2-gram rarity score
        More similar receipts = less rare = lower score
        """
        # Similar logic to prefix rarity
        if similar_count == 0:
            return 1.0
        elif similar_count <= 2:
            return 0.6
        elif similar_count <= 5:
            return 0.3
        else:
            return 0.1
    
    @staticmethod
    def save_anomaly_analysis(
        db: Session,
        receipt_id: str,
        structure: Dict,
        risk_score: float,
        analysis: Dict
    ) -> ReceiptAnomalies:
        """
        Save Layer 4 analysis to receipt_anomalies table
        """
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
        
        logger.info(f"✓ Saved Layer 4 analysis for receipt {receipt_id}: risk={risk_score}")
        
        return anomaly_record
    
    @staticmethod
    def retroactive_risk_update(
        db: Session,
        new_receipt_structure: Dict
    ):
        """
        When a new receipt validates a pattern, go back and reduce risk
        of older receipts with the same pattern
        
        This is the key "learning" mechanism:
        - Day 1: Solo receipt = high risk (0.8)
        - Day 5: Second similar receipt arrives
        - → Go back and reduce Day 1 receipt risk to 0.6
        - Day 10: Third similar receipt arrives
        - → Reduce all three to 0.2 (validated cluster)
        """
        # Find all similar receipts (including older ones)
        cutoff_date = datetime.utcnow() - timedelta(days=AnomalyService.SLIDING_WINDOW_DAYS)
        
        similar_receipts = AnomalyService.find_similar_patterns(
            db,
            new_receipt_structure,
            exclude_receipt_id=None  # Include all
        )
        
        if len(similar_receipts) < 2:
            # Not enough receipts to update (need at least 2 to form a pattern)
            return
        
        # Calculate new risk based on cluster size
        cluster_size = len(similar_receipts)
        
        if cluster_size == 2:
            new_risk = AnomalyService.RISK_SCORES["pair"]
        elif cluster_size == 3:
            new_risk = AnomalyService.RISK_SCORES["triplet"]
        else:
            new_risk = AnomalyService.RISK_SCORES["cluster"]
        
        # Update all receipts in the cluster
        updated_count = 0
        for similar in similar_receipts:
            anomaly_record = db.query(ReceiptAnomalies).filter(
                ReceiptAnomalies.receipt_id == similar["receipt_id"]
            ).first()
            
            if anomaly_record and anomaly_record.layer4_risk_score > new_risk:
                old_risk = anomaly_record.layer4_risk_score
                anomaly_record.layer4_risk_score = new_risk
                
                # Update rarity scores
                anomaly_record.prefix_rarity_score = AnomalyService._calculate_prefix_rarity(cluster_size - 1)
                anomaly_record.digram_rarity_score = AnomalyService._calculate_digram_rarity(cluster_size - 1)
                
                updated_count += 1
                logger.info(f"🔄 Updated receipt {similar['receipt_id']}: {old_risk:.2f} → {new_risk:.2f}")
        
        if updated_count > 0:
            db.commit()
            logger.info(f"✓ Retroactively updated {updated_count} receipts in cluster")
    
    @staticmethod
    def analyze_receipt_id(
        db: Session,
        receipt_id: str,
        easyocr_text: str,
        google_vision_text: str
    ) -> Dict:
        """
        Complete Layer 4 analysis workflow
        
        Steps:
        1. Extract receipt ID from OCR text
        2. Analyze structure
        3. Check for duplicates
        4. Find similar patterns
        5. Calculate risk score
        6. Save to database
        7. Perform retroactive updates
        
        Returns: Complete analysis result
        """
        logger.info(f"Starting Layer 4 analysis for receipt {receipt_id}")
        
        # Step 1: Extract receipt ID
        extracted_id, ocr_confidence = AnomalyService.extract_receipt_id_from_ocr(
            easyocr_text,
            google_vision_text
        )
        
        if not extracted_id:
            return {
                "success": False,
                "error": "Could not extract receipt ID from OCR",
                "layer4_risk_score": 0.9,  # High risk if no ID found
                "assessment": "no_receipt_id_found"
            }
        
        # Step 2: Analyze structure
        structure = AnomalyService.analyze_structure(extracted_id)
        
        if not structure["valid_format"]:
            return {
                "success": False,
                "error": "Receipt ID format invalid",
                "extracted_receipt_id": extracted_id,
                "layer4_risk_score": 0.85,
                "assessment": "invalid_format"
            }
        
        # Step 3: Check for duplicates (exclude current receipt)
        is_duplicate, original_receipt_id = AnomalyService.check_duplicate(
            db, 
            extracted_id,
            receipt_id  # Pass current receipt UUID to exclude it
        )
        
        # Step 4: Find similar patterns
        similar_receipts = AnomalyService.find_similar_patterns(db, structure, exclude_receipt_id=receipt_id)
        
        # Step 5: Calculate risk score
        risk_score, analysis = AnomalyService.calculate_risk_score(
            is_duplicate,
            len(similar_receipts),
            structure
        )
        
        # Step 6: Save to database
        AnomalyService.save_anomaly_analysis(
            db,
            receipt_id,
            structure,
            risk_score,
            analysis
        )
        
        # Step 7: Retroactive updates (if not a duplicate)
        if not is_duplicate and len(similar_receipts) >= 1:
            AnomalyService.retroactive_risk_update(db, structure)
        
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
        """Generate human-readable explanation of what happened"""
        if result.get("is_duplicate"):
            return f"This receipt ID ({result.get('extracted_receipt_id')}) has already been submitted before."
        
        count = result.get("similar_pattern_count", 0)
        structure = result.get("structure", "unknown")
        
        if count == 0:
            return f"This is the first receipt we've seen with this pattern ({structure}). It needs validation from more submissions."
        elif count == 1:
            return f"Found 1 other receipt with a similar pattern. This partially validates it, but more data needed."
        elif count == 2:
            return f"Found 2 other receipts with matching patterns. Pattern is emerging as legitimate."
        else:
            return f"Found {count} receipts with matching patterns. This pattern is well-established and validated."

    @staticmethod
    def _get_risk_explanation(assessment: str, risk: float) -> str:
        """Explain why this risk score was assigned"""
        explanations = {
            "duplicate_fraud": "Exact duplicate = maximum fraud risk (1.0)",
            "solo_pattern": "No similar patterns found = high risk (0.8) - could be fabricated",
            "pair_pattern": "Only 1 similar receipt = medium-high risk (0.6) - needs more validation",
            "triplet_pattern": "2 similar receipts found = medium risk (0.4) - pattern emerging",
            "validated_cluster": "3+ similar receipts = low risk (0.2) - pattern validated by multiple submissions"
        }
        return explanations.get(assessment, f"Risk score: {risk}")

    @staticmethod
    def _get_next_steps(assessment: str) -> str:
        """Suggest what happens next"""
        if assessment == "duplicate_fraud":
            return "⛔ Automatically rejected. Contact admin if you believe this is an error."
        elif assessment == "solo_pattern":
            return "🔍 Flagged for admin review. If legitimate, future similar receipts will validate this pattern."
        elif assessment in ["pair_pattern", "triplet_pattern"]:
            return "⚠️ Flagged for admin review. Pattern is emerging but not yet fully validated."
        else:  # validated_cluster
            return "✅ Pattern validated. Receipt can be auto-approved (pending other layer checks)."
        