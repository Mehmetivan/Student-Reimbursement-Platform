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

    # Software that definitively indicates post-capture editing — high risk
    EDITING_SOFTWARE = [
        "photoshop",
        "gimp",
        "paint.net",
        "affinity",
        "lightroom",
        "snapseed",
        "pixlr",
        "photoscape",
        "fotor",
        "photopea",
        "canva",
        "illustrator",
        "inkscape",
    ]

    # Legitimate camera processing software — NOT editing, do not flag
    # These are written automatically by the camera/phone, not by the user
    CAMERA_SOFTWARE_WHITELIST = [
        "hdr+",
        "hdr",
        "night sight",
        "night mode",
        "portrait mode",
        "google camera",
        "pixel camera",
        "gcam",
        "samsung camera",
        "ios",
        "android",
        "firmware",
        "camera",
        "iphone",
        "samsung",
        "google",
        "huawei",
        "xiaomi",
        "miui",
        "oppo",
        "vivo",
        "oneplus",
    ]

    # Known mobile camera manufacturers
    MOBILE_BRANDS = [
        "iphone", "samsung", "google", "huawei", "xiaomi",
        "oppo", "vivo", "oneplus", "motorola", "nokia"
    ]

    # Days after which a DateTime vs DateTimeOriginal gap becomes suspicious
    TIMESTAMP_GAP_SUSPICIOUS_DAYS = 5

    @staticmethod
    def extract_exif(file_path: Path) -> Dict:
        """Extract EXIF metadata from image file."""
        try:
            image = Image.open(file_path)
            exif_data = image._getexif()
            if not exif_data:
                return {}
            exif_dict = {}
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if isinstance(value, bytes):
                    exif_dict[tag] = value.decode('utf-8', errors='ignore')
                elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):
                    try:
                        exif_dict[tag] = float(value)
                    except Exception:
                        exif_dict[tag] = str(value)
                elif isinstance(value, (list, tuple)):
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
        Check if image was edited with known photo editing software.
        Uses a two-step approach:
        1. If software is in the whitelist (camera processing) → not editing
        2. If software is in the editing list → flag as edited
        Returns: (is_edited, software_name)
        """
        software_fields = ['Software', 'ProcessingSoftware', 'HostComputer']

        for field in software_fields:
            if field in exif_data:
                software = str(exif_data[field]).lower()

                # Step 1: Check whitelist first — if it's camera software, skip
                is_camera_software = any(
                    safe in software for safe in ExifService.CAMERA_SOFTWARE_WHITELIST
                )
                if is_camera_software:
                    continue

                # Step 2: Check against known editing software
                for editor in ExifService.EDITING_SOFTWARE:
                    if editor in software:
                        return True, exif_data[field]

                # Step 3: Unknown software that is not camera software
                # Only flag if the software name is meaningful (not empty/short)
                if len(software.strip()) > 3:
                    return True, exif_data[field]

        return False, None

    @staticmethod
    def check_mobile_camera(exif_data: Dict) -> Tuple[bool, Optional[str]]:
        """Check if photo was taken with a mobile device."""
        for field in ['Model', 'Make']:
            if field in exif_data:
                model = str(exif_data[field]).lower()
                for brand in ExifService.MOBILE_BRANDS:
                    if brand in model:
                        return True, exif_data[field]
        return False, None

    @staticmethod
    def get_photo_age_days(exif_data: Dict) -> Optional[int]:
        """Calculate how old the photo is based on DateTimeOriginal."""
        for field in ['DateTimeOriginal', 'DateTimeDigitized', 'DateTime']:
            if field in exif_data:
                try:
                    datetime_str = str(exif_data[field])
                    photo_datetime = datetime.strptime(datetime_str, "%Y:%m:%d %H:%M:%S")
                    return (datetime.now() - photo_datetime).days
                except Exception as e:
                    logger.warning(f"Could not parse datetime {exif_data[field]}: {e}")
                    continue
        return None

    @staticmethod
    def check_timestamp_gap(exif_data: Dict) -> Tuple[bool, Optional[int]]:
        """
        Check if DateTime (last modified) differs from DateTimeOriginal (capture time).
        A gap larger than TIMESTAMP_GAP_SUSPICIOUS_DAYS suggests the file was
        opened and modified after being taken.

        Note: Small gaps (< 5 days) are not flagged to account for normal behavior
        such as cropping shortly before submission or delayed submission.

        Returns: (is_suspicious, gap_in_days)
        """
        dt_modified_str = exif_data.get('DateTime')
        dt_original_str = exif_data.get('DateTimeOriginal')

        if not dt_modified_str or not dt_original_str:
            return False, None

        try:
            dt_modified = datetime.strptime(str(dt_modified_str), "%Y:%m:%d %H:%M:%S")
            dt_original = datetime.strptime(str(dt_original_str), "%Y:%m:%d %H:%M:%S")
            gap_days = abs((dt_modified - dt_original).days)

            if gap_days > ExifService.TIMESTAMP_GAP_SUSPICIOUS_DAYS:
                logger.info(f"Timestamp gap detected: {gap_days} days between capture and last modification")
                return True, gap_days

            return False, gap_days
        except Exception as e:
            logger.warning(f"Could not compare timestamps: {e}")
            return False, None

    @staticmethod
    def analyze_exif(file_path: Path) -> Dict:
        """
        Complete Layer 2 EXIF analysis.

        Risk scoring (additive, capped at 1.0):
        - No EXIF at all:                    0.8  (high — legitimate photos always have EXIF)
        - Known editing software:            +0.7 (Photopea, Photoshop, GIMP etc.)
        - Timestamp gap > 5 days:            +0.1 (file modified significantly after capture)
        - DateTime missing but orig present: +0.1 (Windows crop or similar stripping)
        - Not from mobile camera:            +0.1 (receipts should come from phones)

        All cases result in manual review flag, never automatic rejection.
        """
        exif_data = ExifService.extract_exif(file_path)

        risk_score = 0.0
        flags = []
        timestamp_inconsistency = False
        gap_days = None

        exif_exists = bool(exif_data)

        # ── No EXIF ──────────────────────────────────────────────────────────
        if not exif_exists:
            risk_score += 0.8
            flags.append("no_exif_data")
            exif_status = "missing"

            return {
                "exif_status": exif_status,
                "exif_exists": False,
                "has_editing_software": False,
                "editing_software": None,
                "is_mobile_camera": False,
                "camera_model": None,
                "photo_age_days": None,
                "risk_score": min(round(risk_score, 2), 1.0),
                "flags": flags,
                "assessment": "high_risk",
                "has_inconsistencies": False,
                "timestamp_inconsistency": False,
                "timestamp_gap_days": None,
            }

        exif_status = "present"

        # ── Editing software ──────────────────────────────────────────────────
        is_edited, software_name = ExifService.check_editing_software(exif_data)
        if is_edited:
            risk_score += 0.7
            flags.append("post_capture_editing_detected")

        # ── Mobile camera check ───────────────────────────────────────────────
        is_mobile, camera_model = ExifService.check_mobile_camera(exif_data)
        if not is_mobile:
            risk_score += 0.1
            flags.append("not_mobile_camera")

        # ── Timestamp gap check ───────────────────────────────────────────────
        timestamp_inconsistency, gap_days = ExifService.check_timestamp_gap(exif_data)
        if timestamp_inconsistency:
            risk_score += 0.1
            flags.append(f"timestamp_gap_{gap_days}_days")

        # ── DateTime missing but DateTimeOriginal present ─────────────────────
        # Happens when tools like Windows Photos strip DateTime on save
        if 'DateTime' not in exif_data and 'DateTimeOriginal' in exif_data:
            risk_score += 0.1
            flags.append("missing_datetime")

        # ── Base risk for clean legitimate photo ──────────────────────────────
        if not flags:
            risk_score = 0.1  # Clean photo — minimal base risk

        # ── Final assessment ──────────────────────────────────────────────────
        risk_score = min(round(risk_score, 2), 1.0)

        if risk_score >= 0.7:
            assessment = "high_risk"
        elif risk_score >= 0.4:
            assessment = "medium_risk"
        else:
            assessment = "low_risk"

        photo_age = ExifService.get_photo_age_days(exif_data)

        return {
            "exif_status": exif_status,
            "exif_exists": True,
            "has_editing_software": is_edited,
            "editing_software": software_name if is_edited else None,
            "is_mobile_camera": is_mobile,
            "camera_model": camera_model,
            "photo_age_days": photo_age,
            "risk_score": risk_score,
            "flags": flags,
            "assessment": assessment,
            "has_inconsistencies": bool(flags),
            "timestamp_inconsistency": timestamp_inconsistency,
            "timestamp_gap_days": gap_days,
        }
