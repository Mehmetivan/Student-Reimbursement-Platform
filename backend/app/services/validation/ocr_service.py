# app/services/validation/ocr_service.py
import pytesseract
from PIL import Image, ImageEnhance
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
        Extract all text from image using Tesseract OCR with preprocessing
        Returns: Raw text extracted from image
        """
        try:
            image = Image.open(file_path)
            
            # Convert to grayscale for better OCR
            image = image.convert('L')
            
            # Increase contrast to improve text recognition
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2)
            
            # Perform OCR with optimized configuration
            # --oem 3: Use default OCR Engine Mode
            # --psm 6: Assume a single uniform block of text
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(image, lang='eng', config=custom_config)
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return ""
    
    @staticmethod
    def extract_stpt_id(text: str) -> Tuple[Optional[str], float]:
        """
        Extract STPT card ID from receipt text
        Looking for pattern: "SERIE CARD:123456" where ID is 6-10 digits
        Handles OCR errors like missing 'D', missing spaces, missing colons
        
        Returns: (stpt_id, confidence)
        """
        logger.info(f"Searching for STPT ID in text: {text[:200]}...")  # Log first 200 chars
        
        # Create a version without spaces for flexible matching
        text_no_spaces = text.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', '')
        
        # Pattern variations to match - well-formatted text
        # Looking for "SERIE CARD" (or variations) followed by digits only
        patterns_formatted = [
            (r'SERIE\s*CARD\s*[:\-]?\s*(\d{6,10})', 0.95, "SERIE CARD (perfect)"),      # SERIE CARD:123456
            (r'SERIE\s*CAR\s*[:\-]?\s*(\d{6,10})', 0.85, "SERIE CAR (missing D)"),      # SERIE CAR:123456
            (r'SERI[EO]\s*CARD\s*[:\-]?\s*(\d{6,10})', 0.80, "SERI* CARD"),            # SERIO CARD:123456
            (r'SERIE\s*C[AO]RD\s*[:\-]?\s*(\d{6,10})', 0.80, "SERIE C*RD"),            # SERIE CORD:123456
        ]
        
        # Pattern variations for poorly OCR'd text (no spaces, possibly missing letters)
        patterns_compact = [
            (r'SERIECARD[:\-]?(\d{6,10})', 0.75, "SERIECARD (compact)"),                # SERIECARD123456
            (r'SERIECAR[:\-]?(\d{6,10})', 0.70, "SERIECAR (compact, missing D)"),      # SERIECAR123456
            (r'SERI[EO]CARD[:\-]?(\d{6,10})', 0.65, "SERI*CARD (compact)"),            # SERIOCARD123456
            (r'SERIEC[AO]RD[:\-]?(\d{6,10})', 0.65, "SERIEC*RD (compact)"),            # SERIECORD123456
            # Even more flexible - just SERIE or CARD followed by digits
            (r'SERIE[A-Z]{0,4}[:\-]?(\d{6,10})', 0.50, "SERIE* (flexible)"),           # SERIEXXXX123456
            (r'CARD[:\-]?(\d{6,10})', 0.40, "CARD (very flexible)"),                    # CARD123456
        ]
        
        # Try well-formatted patterns first (higher confidence)
        for pattern, confidence, label in patterns_formatted:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                stpt_id = match.group(1)
                logger.info(f"✓ Found STPT ID: {stpt_id} using pattern '{label}' (confidence: {confidence})")
                return stpt_id, confidence
        
        # Try compact patterns on text without spaces (lower confidence)
        for pattern, confidence, label in patterns_compact:
            match = re.search(pattern, text_no_spaces, re.IGNORECASE)
            if match:
                stpt_id = match.group(1)
                logger.info(f"✓ Found STPT ID: {stpt_id} using pattern '{label}' (confidence: {confidence})")
                return stpt_id, confidence
        
        # No pattern matched
        logger.warning("✗ No STPT ID pattern matched")
        logger.debug(f"Original text: {text[:150]}...")
        logger.debug(f"Text without spaces: {text_no_spaces[:150]}...")
        return None, 0.0
    
    @staticmethod
    def extract_receipt_id(text: str) -> Tuple[Optional[str], float]:
        """
        Extract receipt transaction ID from text
        Common patterns: TR20250215001234, REC-123456, etc.
        Note: Receipt IDs are typically alphanumeric (letters + digits)
        
        Returns: (receipt_id, confidence)
        """
        logger.info(f"Searching for Receipt ID in text...")
        
        patterns = [
            (r'(TR\d{14})', 0.9, "TR format"),                                    # TR20250215001234
            (r'RECEIPT\s*[:\-]?\s*([A-Z0-9\-]{8,20})', 0.8, "RECEIPT keyword"),   # RECEIPT:ABC-123
            (r'TRANSACTION\s*[:\-]?\s*([A-Z0-9\-]{8,20})', 0.8, "TRANSACTION"),   # TRANSACTION:123
            (r'REF\s*[:\-]?\s*([A-Z0-9\-]{8,20})', 0.7, "REF keyword"),           # REF:ABC-123
            (r'ID\s*[:\-]?\s*([A-Z0-9\-]{8,20})', 0.6, "ID keyword"),             # ID:123456
        ]
        
        for pattern, confidence, label in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                receipt_id = match.group(1)
                logger.info(f"✓ Found Receipt ID: {receipt_id} using pattern '{label}' (confidence: {confidence})")
                return receipt_id, confidence
        
        logger.warning("✗ No Receipt ID pattern matched")
        return None, 0.0
    
    @staticmethod
    def analyze_receipt_text(file_path: Path) -> Dict:
        """
        Complete Layer 3 OCR analysis
        Extracts and validates receipt information
        
        Returns: Analysis result with extracted IDs and confidence scores
        """
        logger.info(f"Starting OCR analysis on: {file_path}")
        
        # Extract raw text
        raw_text = OCRService.extract_text(file_path)
        
        if not raw_text:
            logger.error("OCR extraction failed - no text extracted")
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
        
        logger.info(f"OCR extracted {len(raw_text)} characters")
        logger.debug(f"Raw text preview: {raw_text[:200]}...")
        
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
        
        result = {
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
        
        logger.info(f"OCR Analysis complete. Risk score: {result['risk_score']}, Flags: {flags}")
        
        return result