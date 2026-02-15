# app/services/validation/exif_service.py
from PIL import Image
from PIL.ExifTags import TAGS
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class ExifService:
    """Layer 2: EXIF Metadata Analysis for fraud detection"""
    
    # Software that indicates image editing (high risk)
    EDITING_SOFTWARE = [
        "photoshop",
        "gimp",
        "paint.net",
        "affinity",
        "lightroom",
        "snapseed",
        "pixlr",
        "photoscape",
        "fotor"
    ]
    
    # Known mobile camera manufacturers (legitimate)
    MOBILE_BRANDS = [
        "iphone",
        "samsung",
        "google",
        "huawei",
        "xiaomi",
        "oppo",
        "vivo",
        "oneplus",
        "motorola",
        "nokia"
    ]
    
    @staticmethod
    def extract_exif(file_path: Path) -> Dict:
        """
        Extract EXIF metadata from image file
        Returns: Dictionary with EXIF data or empty dict if no EXIF
        """
        try:
            image = Image.open(file_path)
            exif_data = image._getexif()
            
            if not exif_data:
                return {}
            
            # Convert EXIF tags to readable format and make JSON-serializable
            exif_dict = {}
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                
                # Convert special EXIF types to JSON-serializable formats
                if isinstance(value, bytes):
                    # Convert bytes to string (hex representation)
                    exif_dict[tag] = value.decode('utf-8', errors='ignore')
                elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):
                    # Convert IFDRational to float or string
                    try:
                        exif_dict[tag] = float(value)
                    except:
                        exif_dict[tag] = str(value)
                elif isinstance(value, (list, tuple)):
                    # Convert lists/tuples containing special types
                    exif_dict[tag] = str(value)
                else:
                    exif_dict[tag] = value
            
            return exif_dict
            
        except Exception as e:
            logger.error(f"Error extracting EXIF from {file_path}: {e}")
            return {}
    
    @staticmethod
    def check_editing_software(exif_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if image was edited with photo editing software
        Returns: (is_edited, software_name)
        """
        software_fields = ['Software', 'ProcessingSoftware', 'HostComputer']
        
        for field in software_fields:
            if field in exif_data:
                software = str(exif_data[field]).lower()
                
                for editor in ExifService.EDITING_SOFTWARE:
                    if editor in software:
                        return True, exif_data[field]
        
        return False, None
    
    @staticmethod
    def check_mobile_camera(exif_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if photo was taken with a mobile device
        Returns: (is_mobile, camera_model)
        """
        model_fields = ['Model', 'Make']
        
        for field in model_fields:
            if field in exif_data:
                model = str(exif_data[field]).lower()
                
                for brand in ExifService.MOBILE_BRANDS:
                    if brand in model:
                        return True, exif_data[field]
        
        return False, None
    
    @staticmethod
    def get_photo_age_days(exif_data: Dict) -> Optional[int]:
        """
        Calculate how old the photo is based on EXIF datetime
        Returns: Age in days or None if no datetime available
        """
        datetime_fields = ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']
        
        for field in datetime_fields:
            if field in exif_data:
                try:
                    # EXIF datetime format: "2025:02:15 14:30:45"
                    datetime_str = str(exif_data[field])
                    photo_datetime = datetime.strptime(datetime_str, "%Y:%m:%d %H:%M:%S")
                    age = (datetime.now() - photo_datetime).days
                    return age
                except Exception as e:
                    logger.warning(f"Could not parse datetime {exif_data[field]}: {e}")
                    continue
        
        return None
    
    @staticmethod
    def check_exif_inconsistencies(exif_data: Dict) -> Tuple[bool, list]:
        """
        Detect EXIF manipulation or inconsistencies
        """
        flags = []
        
        # Check 1: Has software field but no camera model (suspicious)
        if 'Software' in exif_data and 'Model' not in exif_data:
            flags.append("software_without_camera_model")
        
        # Check 2: Missing standard camera fields
        camera_fields = ['Make', 'Model']
        missing_fields = [f for f in camera_fields if f not in exif_data]
        
        if len(missing_fields) >= 1 and 'DateTime' in exif_data:
            # Has datetime but missing camera info
            flags.append("incomplete_camera_data")
        
        # Check 3: Multiple datetime fields with different values
        dt_original = exif_data.get('DateTimeOriginal')
        dt_digitized = exif_data.get('DateTimeDigitized')
        
        if dt_original and dt_digitized and dt_original != dt_digitized:
            flags.append("inconsistent_timestamps")
        
        return len(flags) > 0, flags
    
    @staticmethod
    def check_any_software(exif_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check for ANY software mention (not just known editors)
        Uses whitelist approach - flag anything that's NOT camera firmware
        """
        software_fields = ['Software', 'ProcessingSoftware']
        
        # Whitelist: Safe software that should be in photos
        safe_patterns = [
            'ios', 'android', 'firmware', 'camera',
            'iphone', 'samsung', 'google', 'huawei'
        ]
        
        for field in software_fields:
            if field in exif_data:
                software = str(exif_data[field]).lower()
                
                # Check if it's safe software
                is_safe = any(safe in software for safe in safe_patterns)
                
                if not is_safe and len(software) > 2:
                    # Unknown software detected
                    return True, exif_data[field]
        
        return False, None
    
    @staticmethod
    def analyze_exif(file_path: Path) -> Dict:
        """
        Complete Layer 2 EXIF analysis with enhanced detection
        Returns: Analysis result with risk score and flags
        """
        # Extract EXIF data
        exif_data = ExifService.extract_exif(file_path)
        
        risk_score = 0.0
        flags = []
        
        # Check if EXIF exists
        exif_exists = bool(exif_data)
        
        if not exif_exists:
            # No EXIF = likely screenshot or heavily processed
            risk_score += 0.4
            flags.append("no_exif_data")
            exif_status = "missing"
        else:
            exif_status = "present"
        
        # Check for known editing software (high confidence)
        is_edited, software_name = ExifService.check_editing_software(exif_data)
        if is_edited:
            risk_score += 0.5
            flags.append("known_editing_software")
        
        # Check if from mobile camera
        is_mobile, camera_model = ExifService.check_mobile_camera(exif_data)
        
        # Check for ANY suspicious software (medium confidence)
        has_unknown_software, unknown_software = ExifService.check_any_software(exif_data)
        if has_unknown_software and not is_edited:
            # Unknown software detected
            software_name = unknown_software
            
            # CRITICAL: If camera model exists BUT software was used = EDITED AFTER CAPTURE
            if is_mobile and camera_model:
                # This is the smoking gun! Photo was taken with phone, then edited
                risk_score += 0.6  # Very high risk!
                flags.append("post_capture_editing_detected")
            else:
                risk_score += 0.3
                flags.append("unknown_software_detected")
        
        # Check for EXIF inconsistencies
        has_inconsistencies, inconsistency_flags = ExifService.check_exif_inconsistencies(exif_data)
        if has_inconsistencies:
            risk_score += 0.25
            flags.extend(inconsistency_flags)
        
        if not is_mobile and exif_exists:
            flags.append("not_mobile_camera")
        
        # Check photo age
        photo_age = ExifService.get_photo_age_days(exif_data)
        if photo_age and photo_age > 90:
            risk_score += 0.1
            flags.append("old_photo")
        
        # Check for missing critical fields
        if exif_exists and 'DateTime' not in exif_data:
            risk_score += 0.2
            flags.append("missing_datetime")
        
        # Determine overall assessment
        if risk_score >= 0.7:
            assessment = "high_risk"
        elif risk_score >= 0.4:
            assessment = "medium_risk"
        else:
            assessment = "low_risk"
        
        return {
            "exif_status": exif_status,
            "exif_exists": exif_exists,
            "has_editing_software": is_edited or has_unknown_software,
            "editing_software": software_name,
            "is_mobile_camera": is_mobile,
            "camera_model": camera_model if exif_exists else None,
            "photo_age_days": photo_age,
            "risk_score": risk_score,
            "flags": flags,
            "assessment": assessment,
            "has_inconsistencies": has_inconsistencies,
            "timestamp_inconsistency": False  # Deprecated
        }