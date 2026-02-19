# app/services/validation/ocr_service.py
import pytesseract
from PIL import Image
from pathlib import Path
import re
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Set Tesseract path (Windows default installation)
# If Tesseract is in PATH, comment out this line
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OCRService:
    """Layer 3: OCR & Semantic Checks for receipt validation"""
    
    @staticmethod
    def extract_text(file_path: Path) -> str:
        """
        Extract all text from image using Tesseract OCR
        Returns: Raw text extracted from image
        """
        try:
            image = Image.open(file_path)
            
            # Perform OCR
            text = pytesseract.image_to_string(image, lang='eng')
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return ""
    
    @staticmethod
    def extract_stpt_id(text: str) -> Tuple[Optional[str], float]:
        """
        Extract STPT card ID from receipt text
        Looking for pattern: "SERIE CARD:555845" or variations
        
        Returns: (stpt_id, confidence)
        """
        # Pattern variations to match
        patterns = [
            r'SERIE\s*CARD\s*[:\-]?\s*(\d{6,10})',  # SERIE CARD:555845 or SERIE CARD 555845
            r'CARD\s*ID\s*[:\-]?\s*(\d{6,10})',     # CARD ID:555845
            r'CARD\s*NO\s*[:\-]?\s*(\d{6,10})',     # CARD NO:555845
            r'STPT\s*ID\s*[:\-]?\s*(\d{6,10})',     # STPT ID:555845
            r'STPT\s*CARD\s*[:\-]?\s*(\d{6,10})',   # STPT CARD:555845
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                stpt_id = match.group(1)
                # Confidence is higher for exact "SERIE CARD" match
                confidence = 0.9 if 'SERIE' in pattern else 0.7
                return stpt_id, confidence
        
        # No pattern matched
        return None, 0.0
    
    @staticmethod
    def extract_receipt_id(text: str) -> Tuple[Optional[str], float]:
        """
        Extract receipt transaction ID from text
        Common patterns: TR20250215001234, REC-123456, etc.
        
        Returns: (receipt_id, confidence)
        """
        patterns = [
            r'(TR\d{14})',                    # TR20250215001234
            r'RECEIPT\s*[:\-]?\s*([A-Z0-9\-]{8,20})',  # RECEIPT:ABC-123
            r'TRANSACTION\s*[:\-]?\s*([A-Z0-9\-]{8,20})',
            r'REF\s*[:\-]?\s*([A-Z0-9\-]{8,20})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                receipt_id = match.group(1)
                confidence = 0.8
                return receipt_id, confidence
        
        return None, 0.0
    
    @staticmethod
    def analyze_receipt_text(file_path: Path) -> Dict:
        """
        Complete Layer 3 OCR analysis
        Extracts and validates receipt information
        
        Returns: Analysis result with extracted IDs and confidence scores
        """
        # Extract raw text
        raw_text = OCRService.extract_text(file_path)
        
        if not raw_text:
            return {
                "ocr_successful": False,
                "raw_text": "",
                "stpt_id": None,
                "stpt_id_confidence": 0.0,
                "receipt_id": None,
                "receipt_id_confidence": 0.0,
                "risk_score": 0.5,  # Medium risk if OCR fails
                "flags": ["ocr_failed"]
            }
        
        # Extract STPT ID
        stpt_id, stpt_confidence = OCRService.extract_stpt_id(raw_text)
        
        # Extract receipt ID
        receipt_id, receipt_confidence = OCRService.extract_receipt_id(raw_text)
        
        # Calculate risk score
        risk_score = 0.0
        flags = []
        
        if not stpt_id:
            risk_score += 0.4
            flags.append("stpt_id_not_found")
        elif stpt_confidence < 0.7:
            risk_score += 0.2
            flags.append("stpt_id_low_confidence")
        
        if not receipt_id:
            risk_score += 0.1
            flags.append("receipt_id_not_found")
        
        # Overall OCR confidence
        avg_confidence = (stpt_confidence + receipt_confidence) / 2 if stpt_id or receipt_id else 0.0
        
        if avg_confidence < 0.6:
            risk_score += 0.2
            flags.append("low_ocr_quality")
        
        return {
            "ocr_successful": True,
            "raw_text": raw_text,
            "stpt_id": stpt_id,
            "stpt_id_confidence": stpt_confidence,
            "receipt_id": receipt_id,
            "receipt_id_confidence": receipt_confidence,
            "average_confidence": avg_confidence,
            "risk_score": min(risk_score, 1.0),
            "flags": flags
        }