# app/services/validation/multi_ocr_service.py
import pytesseract
import easyocr
from PIL import Image
from pathlib import Path
import re
import logging
from typing import Dict, Tuple, Optional
from ...config import settings

logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

_easyocr_reader = None

def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        logger.info("Initializing EasyOCR reader...")
        _easyocr_reader = easyocr.Reader(['en'], gpu=False)
    return _easyocr_reader


class MultiOCRService:

    @staticmethod
    def extract_text_tesseract(file_path: Path) -> Dict:
        try:
            start_time = __import__('time').time()
            image = Image.open(file_path).convert('L')
            text = pytesseract.image_to_string(image, lang='eng', config=r'--oem 3 --psm 6')
            return {
                "ocr_engine": "Tesseract",
                "success": True,
                "raw_text": text.strip(),
                "processing_time_seconds": round(__import__('time').time() - start_time, 2),
                "error": None
            }
        except Exception as e:
            logger.error(f"Tesseract OCR error: {e}")
            return {"ocr_engine": "Tesseract", "success": False, "raw_text": "", "processing_time_seconds": 0, "error": str(e)}

    @staticmethod
    def extract_text_easyocr(file_path: Path) -> Dict:
        try:
            start_time = __import__('time').time()
            reader = get_easyocr_reader()
            results = reader.readtext(str(file_path))
            full_text = '\n'.join([text for (_, text, _) in results])
            avg_confidence = sum(conf for (_, _, conf) in results) / len(results) if results else 0.0
            return {
                "ocr_engine": "EasyOCR",
                "success": True,
                "raw_text": full_text,
                "processing_time_seconds": round(__import__('time').time() - start_time, 2),
                "average_confidence": round(avg_confidence, 3),
                "detected_segments": len(results),
                "error": None
            }
        except Exception as e:
            logger.error(f"EasyOCR error: {e}")
            return {"ocr_engine": "EasyOCR", "success": False, "raw_text": "", "processing_time_seconds": 0, "error": str(e)}

    @staticmethod
    def extract_text_google_vision(file_path: Path) -> Dict:
        try:
            start_time = __import__('time').time()
            if not settings.GOOGLE_CLOUD_VISION_API_KEY:
                return {"ocr_engine": "Google Cloud Vision", "success": False, "raw_text": "", "processing_time_seconds": 0, "error": "API key not configured"}

            import requests, base64
            with open(file_path, 'rb') as f:
                content = f.read()
            image_base64 = base64.b64encode(content).decode('utf-8')
            url = f"https://vision.googleapis.com/v1/images:annotate?key={settings.GOOGLE_CLOUD_VISION_API_KEY}"
            payload = {"requests": [{"image": {"content": image_base64}, "features": [{"type": "TEXT_DETECTION"}]}]}
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            text_annotations = result.get('responses', [{}])[0].get('textAnnotations', [])
            full_text = text_annotations[0]['description'] if text_annotations else ""
            return {
                "ocr_engine": "Google Cloud Vision",
                "success": True,
                "raw_text": full_text,
                "processing_time_seconds": round(__import__('time').time() - start_time, 2),
                "detected_segments": len(text_annotations) - 1 if text_annotations else 0,
                "error": None
            }
        except Exception as e:
            logger.error(f"Google Cloud Vision error: {e}")
            return {"ocr_engine": "Google Cloud Vision", "success": False, "raw_text": "", "processing_time_seconds": 0, "error": str(e)}

    @staticmethod
    def extract_stpt_id(text: str) -> Tuple[Optional[str], float]:
        """Extract STPT customer ID from receipt text. Pattern: SERIE CARD: 555845"""
        if not text:
            return None, 0.0
        text_no_spaces = text.replace(' ', '').replace('\n', '')
        patterns = [
            (r'SERIE\s*CARD\s*[:\-]?\s*(\d{6,10})', 0.95),
            (r'SERTE\s*CARD\s*[:\-]?\s*(\d{6,10})', 0.90),
            (r'SERIE\s*CAR\s*[:\-]?\s*(\d{6,10})', 0.85),
            (r'SERIECARD[:\-]?(\d{6,10})', 0.75),
            (r'SERTECARD[:\-]?(\d{6,10})', 0.75),
            (r'CARD[:\-]?\s*(\d{6,10})', 0.50),
        ]
        for pattern, confidence in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1), confidence
            match = re.search(pattern, text_no_spaces, re.IGNORECASE)
            if match:
                return match.group(1), confidence * 0.9
        return None, 0.0

    @staticmethod
    def compare_all_ocr(file_path: Path) -> Dict:
        """
        Run all three OCR engines and compare results.
        Consensus mechanism:
        1. If all 3 agree -> use that result (highest confidence)
        2. If any 2 agree -> use that result (majority)
        3. If none agree -> use the engine with highest confidence score
        """
        logger.info(f"Starting multi-OCR comparison on: {file_path}")

        tesseract_result = MultiOCRService.extract_text_tesseract(file_path)
        easyocr_result = MultiOCRService.extract_text_easyocr(file_path)
        google_vision_result = MultiOCRService.extract_text_google_vision(file_path)
        
        tesseract_stpt, tesseract_conf = MultiOCRService.extract_stpt_id(tesseract_result["raw_text"])
        easyocr_stpt, easyocr_conf = MultiOCRService.extract_stpt_id(easyocr_result["raw_text"])
        google_stpt, google_conf = MultiOCRService.extract_stpt_id(google_vision_result["raw_text"])

        # Apply engine reliability multipliers to pattern confidence scores.
        # Pattern confidence (0.95, 0.90 etc.) only reflects how well the text
        # matched the regex — not how reliable the engine is. These multipliers
        # ensure Google Vision results are trusted more than EasyOCR or Tesseract
        # when engines disagree or only one engine finds the ID.
        tesseract_conf = round(tesseract_conf * 0.70, 3)  # Least reliable
        easyocr_conf = round(easyocr_conf * 0.85, 3)      # Medium reliability
        google_conf = round(google_conf * 1.0, 3)          # Most reliable — unchanged

        tesseract_result["stpt_id_found"] = tesseract_stpt
        tesseract_result["stpt_id_confidence"] = tesseract_conf
        easyocr_result["stpt_id_found"] = easyocr_stpt
        easyocr_result["stpt_id_confidence"] = easyocr_conf
        google_vision_result["stpt_id_found"] = google_stpt
        google_vision_result["stpt_id_confidence"] = google_conf

        # --- Improved consensus mechanism ---
        all_agree = False
        majority_agree = False
        consensus_id = None

        # Step 1: Check if all 3 agree
        if tesseract_stpt and tesseract_stpt == easyocr_stpt == google_stpt:
            consensus_id = tesseract_stpt
            all_agree = True
            majority_agree = True
            agreement_count = 3

        # Step 2: Check if any 2 agree (majority)
        elif tesseract_stpt and tesseract_stpt == easyocr_stpt:
            consensus_id = tesseract_stpt
            majority_agree = True
            agreement_count = 2

        elif tesseract_stpt and tesseract_stpt == google_stpt:
            consensus_id = tesseract_stpt
            majority_agree = True
            agreement_count = 2

        elif easyocr_stpt and easyocr_stpt == google_stpt:
            consensus_id = easyocr_stpt
            majority_agree = True
            agreement_count = 2

        # Step 3: No agreement — use highest confidence
        else:
            best = max(
                [("Tesseract", tesseract_stpt, tesseract_conf),
                 ("EasyOCR", easyocr_stpt, easyocr_conf),
                 ("Google Vision", google_stpt, google_conf)],
                key=lambda x: x[2]
            )
            consensus_id = best[1]
            agreement_count = 1

        return {
            "tesseract": tesseract_result,
            "easyocr": easyocr_result,
            "google_cloud_vision": google_vision_result,
            "consensus": {
                "stpt_id": consensus_id,
                "agreement_count": agreement_count,
                "total_engines": 3,
                "all_agree": all_agree,
                "majority_agree": majority_agree
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
                    [("Tesseract", tesseract_conf),
                     ("EasyOCR", easyocr_conf),
                     ("Google Vision", google_conf)],
                    key=lambda x: x[1]
                )[0] if any([tesseract_conf, easyocr_conf, google_conf]) else None
            }
        }

    @staticmethod
    def extract_stpt_id_from_card(text: str) -> tuple:
        """
        Extract STPT customer ID from physical STPT card image.
        Card format: 09 01 00555845
        Stores full number including leading zeros for substring comparison with receipt.
        """
        if not text:
            return None, 0.0
        pattern = r'\b\d{1,2}\s+\d{1,2}\s+(\d{6,12})\b'
        match = re.search(pattern, text)
        if match:
            raw_id = match.group(1)
            if raw_id:
                return raw_id, 0.90
        stpt_pattern = r'STPT[\s\S]{0,50}?(\d{6,12})'
        match = re.search(stpt_pattern, text, re.IGNORECASE)
        if match:
            raw_id = match.group(1)
            if raw_id:
                return raw_id, 0.70
        return None, 0.0

    @staticmethod
    def extract_card_id(file_path) -> dict:
        """
        Run OCR on STPT card image and extract customer ID.
        Uses Google Vision first, falls back to EasyOCR.
        """
        file_path = Path(file_path)
        google_result = MultiOCRService.extract_text_google_vision(file_path)
        if google_result["success"] and google_result["raw_text"]:
            stpt_id, conf = MultiOCRService.extract_stpt_id_from_card(google_result["raw_text"])
            if stpt_id:
                return {"extracted_stpt_id": stpt_id, "confidence": conf, "raw_text": google_result["raw_text"], "ocr_engine": "google_cloud_vision"}
        easyocr_result = MultiOCRService.extract_text_easyocr(file_path)
        if easyocr_result["success"] and easyocr_result["raw_text"]:
            stpt_id, conf = MultiOCRService.extract_stpt_id_from_card(easyocr_result["raw_text"])
            if stpt_id:
                return {"extracted_stpt_id": stpt_id, "confidence": conf, "raw_text": easyocr_result["raw_text"], "ocr_engine": "easyocr"}
        return {"extracted_stpt_id": None, "confidence": 0.0, "raw_text": google_result.get("raw_text", ""), "ocr_engine": "none"}
