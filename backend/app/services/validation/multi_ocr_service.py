# app/services/validation/multi_ocr_service.py
import pytesseract
import easyocr
from google.cloud import vision
from PIL import Image
from pathlib import Path
import re
import io
import logging
from typing import Dict, List, Tuple, Optional
from ...config import settings
import os

logger = logging.getLogger(__name__)

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Initialize EasyOCR reader (lazy loading for performance)
_easyocr_reader = None

def get_easyocr_reader():
    """Lazy load EasyOCR reader (takes a few seconds on first use)"""
    global _easyocr_reader
    if _easyocr_reader is None:
        logger.info("Initializing EasyOCR reader (this may take a moment)...")
        _easyocr_reader = easyocr.Reader(['en'], gpu=False)
    return _easyocr_reader

class MultiOCRService:
    """
    Multi-OCR Service for comparing different OCR engines
    Implements: Tesseract, EasyOCR, and Google Cloud Vision
    """
    
    @staticmethod
    def extract_text_tesseract(file_path: Path) -> Dict:
        """Extract text using Tesseract OCR"""
        try:
            start_time = __import__('time').time()
            
            image = Image.open(file_path)
            image = image.convert('L')  # Grayscale
            
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(image, lang='eng', config=custom_config)
            
            elapsed_time = __import__('time').time() - start_time
            
            return {
                "ocr_engine": "Tesseract",
                "success": True,
                "raw_text": text.strip(),
                "processing_time_seconds": round(elapsed_time, 2),
                "error": None
            }
        except Exception as e:
            logger.error(f"Tesseract OCR error: {e}")
            return {
                "ocr_engine": "Tesseract",
                "success": False,
                "raw_text": "",
                "processing_time_seconds": 0,
                "error": str(e)
            }
    
    @staticmethod
    def extract_text_easyocr(file_path: Path) -> Dict:
        """Extract text using EasyOCR"""
        try:
            start_time = __import__('time').time()
            
            reader = get_easyocr_reader()
            
            # EasyOCR returns list of (bbox, text, confidence)
            results = reader.readtext(str(file_path))
            
            # Combine all detected text
            text_parts = [text for (bbox, text, conf) in results]
            full_text = '\n'.join(text_parts)
            
            # Calculate average confidence
            avg_confidence = sum(conf for (bbox, text, conf) in results) / len(results) if results else 0.0
            
            elapsed_time = __import__('time').time() - start_time
            
            return {
                "ocr_engine": "EasyOCR",
                "success": True,
                "raw_text": full_text,
                "processing_time_seconds": round(elapsed_time, 2),
                "average_confidence": round(avg_confidence, 3),
                "detected_segments": len(results),
                "error": None
            }
        except Exception as e:
            logger.error(f"EasyOCR error: {e}")
            return {
                "ocr_engine": "EasyOCR",
                "success": False,
                "raw_text": "",
                "processing_time_seconds": 0,
                "error": str(e)
            }
    
    @staticmethod
    def extract_text_google_vision(file_path: Path) -> Dict:
        """Extract text using Google Cloud Vision API"""
        try:
            start_time = __import__('time').time()
            
            if not settings.GOOGLE_CLOUD_VISION_API_KEY:
                return {
                    "ocr_engine": "Google Cloud Vision",
                    "success": False,
                    "raw_text": "",
                    "processing_time_seconds": 0,
                    "error": "API key not configured in .env file"
                }
            
            # Read image file
            with open(file_path, 'rb') as image_file:
                content = image_file.read()
            
            # Use requests library instead of the client library
            import requests
            import base64
            
            # Encode image to base64
            image_base64 = base64.b64encode(content).decode('utf-8')
            
            # Make API request
            url = f"https://vision.googleapis.com/v1/images:annotate?key={settings.GOOGLE_CLOUD_VISION_API_KEY}"
            
            payload = {
                "requests": [
                    {
                        "image": {"content": image_base64},
                        "features": [{"type": "TEXT_DETECTION"}]
                    }
                ]
            }
            
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract text from response
            if 'responses' in result and len(result['responses']) > 0:
                text_annotations = result['responses'][0].get('textAnnotations', [])
                full_text = text_annotations[0]['description'] if text_annotations else ""
            else:
                full_text = ""
            
            elapsed_time = __import__('time').time() - start_time
            
            return {
                "ocr_engine": "Google Cloud Vision",
                "success": True,
                "raw_text": full_text,
                "processing_time_seconds": round(elapsed_time, 2),
                "detected_segments": len(text_annotations) - 1 if text_annotations else 0,
                "error": None
            }
        
        except Exception as e:
            logger.error(f"Google Cloud Vision error: {e}")
            return {
                "ocr_engine": "Google Cloud Vision",
                "success": False,
                "raw_text": "",
                "processing_time_seconds": 0,
                "error": str(e)
            }
    
    @staticmethod
    def extract_stpt_id(text: str) -> Tuple[Optional[str], float]:
        """
        Extract STPT ID from text (same logic as before)
        Pattern: SERIE CARD:555845
        """
        if not text:
            return None, 0.0
        
        text_no_spaces = text.replace(' ', '').replace('\n', '')
        
        patterns = [
            (r'SERIE\s*CARD\s*[:\-]?\s*(\d{6,10})', 0.95),
            (r'SERTE\s*CARD\s*[:\-]?\s*(\d{6,10})', 0.90),  # I->T typo
            (r'SERIE\s*CAR\s*[:\-]?\s*(\d{6,10})', 0.85),
            (r'SERIECARD[:\-]?(\d{6,10})', 0.75),
            (r'SERTECARD[:\-]?(\d{6,10})', 0.75),
            (r'CARD[:\-]?\s*(\d{6,10})', 0.50),
        ]
        
        for pattern, confidence in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1), confidence
            
            # Try without spaces
            match = re.search(pattern, text_no_spaces, re.IGNORECASE)
            if match:
                return match.group(1), confidence * 0.9
        
        return None, 0.0
    
    @staticmethod
    def compare_all_ocr(file_path: Path) -> Dict:
        """
        Run all three OCR engines and compare results
        Returns comparison data for thesis analysis
        """
        logger.info(f"Starting multi-OCR comparison on: {file_path}")
        
        # Run all three OCR engines
        tesseract_result = MultiOCRService.extract_text_tesseract(file_path)
        easyocr_result = MultiOCRService.extract_text_easyocr(file_path)
        google_vision_result = MultiOCRService.extract_text_google_vision(file_path)
        
        # Extract STPT IDs from each
        tesseract_stpt, tesseract_conf = MultiOCRService.extract_stpt_id(tesseract_result["raw_text"])
        easyocr_stpt, easyocr_conf = MultiOCRService.extract_stpt_id(easyocr_result["raw_text"])
        google_stpt, google_conf = MultiOCRService.extract_stpt_id(google_vision_result["raw_text"])
        
        # Add extraction results to each engine's data
        tesseract_result["stpt_id_found"] = tesseract_stpt
        tesseract_result["stpt_id_confidence"] = tesseract_conf
        
        easyocr_result["stpt_id_found"] = easyocr_stpt
        easyocr_result["stpt_id_confidence"] = easyocr_conf
        
        google_vision_result["stpt_id_found"] = google_stpt
        google_vision_result["stpt_id_confidence"] = google_conf
        
        # Determine consensus (if 2+ agree)
        stpt_ids = [tesseract_stpt, easyocr_stpt, google_stpt]
        stpt_ids_found = [id for id in stpt_ids if id is not None]
        
        if len(stpt_ids_found) >= 2:
            # Find most common
            from collections import Counter
            consensus_id = Counter(stpt_ids_found).most_common(1)[0][0]
            consensus_count = stpt_ids_found.count(consensus_id)
        else:
            consensus_id = stpt_ids_found[0] if stpt_ids_found else None
            consensus_count = 1
        
        # Summary comparison
        comparison = {
            "tesseract": tesseract_result,
            "easyocr": easyocr_result,
            "google_cloud_vision": google_vision_result,
            
            "consensus": {
                "stpt_id": consensus_id,
                "agreement_count": consensus_count,
                "total_engines": 3,
                "all_agree": consensus_count == 3,
                "majority_agree": consensus_count >= 2
            },
            
            "performance_comparison": {
                "fastest_engine": min(
                    [tesseract_result, easyocr_result, google_vision_result],
                    key=lambda x: x["processing_time_seconds"] if x["success"] else float('inf')
                )["ocr_engine"],
                
                "total_processing_time": round(
                    tesseract_result["processing_time_seconds"] +
                    easyocr_result["processing_time_seconds"] +
                    google_vision_result["processing_time_seconds"], 2
                ),
                
                "success_rate": sum([
                    tesseract_result["success"],
                    easyocr_result["success"],
                    google_vision_result["success"]
                ]) / 3
            },
            
            "thesis_analysis": {
                "engines_found_stpt_id": sum([
                    tesseract_stpt is not None,
                    easyocr_stpt is not None,
                    google_stpt is not None
                ]),
                "highest_confidence_engine": max(
                    [
                        ("Tesseract", tesseract_conf),
                        ("EasyOCR", easyocr_conf),
                        ("Google Vision", google_conf)
                    ],
                    key=lambda x: x[1]
                )[0] if any([tesseract_conf, easyocr_conf, google_conf]) else None
            }
        }
        
        return comparison