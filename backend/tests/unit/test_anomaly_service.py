# tests/unit/test_anomaly_service.py
import pytest
from app.services.validation.anomaly_service import AnomalyService
from app.database.models.receipt_ocr import ReceiptOCR
from datetime import datetime
from app.database.models.receipt import Receipt
from app.database.models.request import Request, RequestStatus
from app.database.models.student import Student
from app.database.models.user import User, UserRole
from app.database.models.receipt_anomalies import ReceiptAnomalies
from app.database.models.receipt_risk_assessment import ReceiptRiskAssessment

class TestExtractReceiptIdFromOcr:
    """Tests for receipt ID extraction from OCR text."""

    def test_both_engines_agree_high_confidence(self):
        """
        TEST CASE: When both OCR engines extract the same receipt ID,
        confidence should be highest (0.95).
        WHY: Agreement between independent OCR engines is the strongest
        signal that the extracted ID is correct.
        """
        text = "Receipt 324-19204-128165 STPT"
        extracted_id, confidence = AnomalyService.extract_receipt_id_from_ocr(text, text)
        assert extracted_id == "324-19204-128165"
        assert confidence == 0.95

    def test_engines_disagree_uses_google_with_lower_confidence(self):
        """
        TEST CASE: When EasyOCR and Google Vision extract different IDs,
        use Google Vision's result with reduced confidence (0.6).
        WHY: Google Vision was empirically more accurate in our evaluation,
        so its result takes precedence, but confidence drops to reflect
        the disagreement.
        """
        easyocr_text = "Receipt 1324-19204-128165"
        google_text = "Receipt 324-19204-128165"
        extracted_id, confidence = AnomalyService.extract_receipt_id_from_ocr(
            easyocr_text, google_text
        )
        assert extracted_id == "324-19204-128165"
        assert confidence == 0.6

    def test_only_google_finds_id(self):
        """
        TEST CASE: When only Google Vision extracts an ID, use it with
        confidence 0.7.
        WHY: Google Vision is the primary engine. If only it found the ID,
        the result is usable but unconfirmed by the second engine.
        """
        easyocr_text = "garbled text no id here"
        google_text = "Receipt 324-19204-128165"
        extracted_id, confidence = AnomalyService.extract_receipt_id_from_ocr(
            easyocr_text, google_text
        )
        assert extracted_id == "324-19204-128165"
        assert confidence == 0.7

    def test_only_easyocr_finds_id(self):
        """
        TEST CASE: When only EasyOCR extracts an ID, use it with
        lowest confidence (0.55).
        WHY: EasyOCR is the fallback engine. Without Google Vision's
        confirmation, confidence is lowest but the ID is still usable.
        """
        easyocr_text = "Receipt 324-19204-128165"
        google_text = "garbled text no id here"
        extracted_id, confidence = AnomalyService.extract_receipt_id_from_ocr(
            easyocr_text, google_text
        )
        assert extracted_id == "324-19204-128165"
        assert confidence == 0.55

    def test_no_id_found_returns_none(self):
        """
        TEST CASE: When neither engine extracts an ID, return None with 0.0.
        WHY: This case must be handled — the receipt cannot be analyzed
        in Layer 4 and is escalated to high risk in the calling pipeline.
        """
        extracted_id, confidence = AnomalyService.extract_receipt_id_from_ocr(
            "no id text", "also no id"
        )
        assert extracted_id is None
        assert confidence == 0.0


class TestAnalyzeStructure:
    """Tests for receipt ID structural analysis."""

    def test_valid_receipt_id_is_parsed_correctly(self):
        """
        TEST CASE: A receipt ID matching the expected pattern
        (3-4 digits)-(5-6 digits)-(6-7 digits) must be parsed into its components.
        WHY: All downstream similarity checks rely on this parsing.
        If parsing is wrong, the n-gram analysis and stand indicator
        comparison would produce meaningless results.
        """
        result = AnomalyService.analyze_structure("324-19204-128165")
        assert result["valid_format"] is True
        assert result["prefix"] == "324"
        assert result["middle"] == "19204"
        assert result["last"] == "128165"
        assert result["structure_pattern"] == "3-5-6"
        assert result["stand_indicator"] == "32"

    def test_invalid_format_returns_false(self):
        """
        TEST CASE: A string that doesn't match the receipt ID pattern
        must return valid_format=False.
        WHY: The pipeline must distinguish receipt IDs from random text
        to avoid analyzing malformed data.
        """
        result = AnomalyService.analyze_structure("not-a-receipt-id")
        assert result["valid_format"] is False

    def test_digrams_are_extracted_correctly(self):
        """
        TEST CASE: For a receipt ID, the digrams (2-character substrings)
        must be extracted from all digits combined.
        WHY: The n-gram overlap analysis is the core of Layer 4 similarity
        detection. Correct digram extraction is essential for clustering
        receipts with similar patterns even when OCR has minor errors.
        """
        result = AnomalyService.analyze_structure("123-45678-901234")
        # All digits: 12345678901234
        # Digrams: 12, 23, 34, 45, 56, 67, 78, 89, 90, 01, 12, 23, 34
        expected_digrams = ["12", "23", "34", "45", "56", "67", "78", "89",
                            "90", "01", "12", "23", "34"]
        assert result["digrams"] == expected_digrams


class TestCalculateRiskScore:
    """Tests for risk score assignment based on similarity count."""

    def _structure(self):
        """Helper to provide a valid structure dict for tests."""
        return AnomalyService.analyze_structure("324-19204-128165")

    def test_duplicate_gets_maximum_risk(self):
        """
        TEST CASE: When the receipt ID is a duplicate, risk score must be 1.0.
        WHY: An exact duplicate receipt ID is the strongest fraud signal
        in Layer 4 — the same receipt has already been submitted.
        """
        risk, analysis = AnomalyService.calculate_risk_score(
            is_duplicate=True, similar_count=0, structure=self._structure()
        )
        assert risk == 1.0
        assert analysis["assessment"] == "duplicate_fraud"

    def test_solo_pattern_gets_high_risk(self):
        """
        TEST CASE: When no similar patterns exist (similar_count=0),
        risk score is 0.8 — high risk for a never-before-seen pattern.
        WHY: A receipt ID with no similar structure could be fabricated.
        It needs to be flagged for review until more similar receipts
        validate the pattern as legitimate.
        """
        risk, analysis = AnomalyService.calculate_risk_score(
            is_duplicate=False, similar_count=0, structure=self._structure()
        )
        assert risk == 0.8
        assert analysis["assessment"] == "solo_pattern"

    def test_pair_pattern_gets_medium_high_risk(self):
        """
        TEST CASE: 1 similar receipt found → risk 0.6 (pair pattern).
        WHY: One match starts validating the pattern but is not enough
        evidence on its own.
        """
        risk, analysis = AnomalyService.calculate_risk_score(
            is_duplicate=False, similar_count=1, structure=self._structure()
        )
        assert risk == 0.6
        assert analysis["assessment"] == "pair_pattern"

    def test_triplet_pattern_gets_medium_risk(self):
        """
        TEST CASE: 2 similar receipts found → risk 0.4 (triplet pattern).
        WHY: Pattern is emerging as legitimate as more receipts share it.
        """
        risk, analysis = AnomalyService.calculate_risk_score(
            is_duplicate=False, similar_count=2, structure=self._structure()
        )
        assert risk == 0.4
        assert analysis["assessment"] == "triplet_pattern"

    def test_validated_cluster_gets_low_risk(self):
        """
        TEST CASE: 3 or more similar receipts → risk 0.2 (validated cluster).
        WHY: A pattern shared by many receipts is well-established as legitimate
        — likely a valid receipt format from the actual STPT system.
        """
        risk, analysis = AnomalyService.calculate_risk_score(
            is_duplicate=False, similar_count=5, structure=self._structure()
        )
        assert risk == 0.2
        assert analysis["assessment"] == "validated_cluster"


class TestRarityScores:
    """Tests for the prefix and digram rarity scoring helpers."""

    def test_prefix_rarity_decreases_with_more_matches(self):
        """
        TEST CASE: Prefix rarity score should decrease as more similar
        receipts are found (rarer → higher score).
        WHY: A unique prefix is rarer and more suspicious. As more
        receipts share the prefix, rarity drops and so should the score.
        """
        assert AnomalyService._calculate_prefix_rarity(0) == 1.0
        assert AnomalyService._calculate_prefix_rarity(2) == 0.7
        assert AnomalyService._calculate_prefix_rarity(5) == 0.4
        assert AnomalyService._calculate_prefix_rarity(10) == 0.1

    def test_digram_rarity_decreases_with_more_matches(self):
        """
        TEST CASE: Digram rarity score follows the same decreasing pattern.
        WHY: Same reasoning as prefix rarity — common patterns are less
        suspicious than rare ones.
        """
        assert AnomalyService._calculate_digram_rarity(0) == 1.0
        assert AnomalyService._calculate_digram_rarity(2) == 0.6
        assert AnomalyService._calculate_digram_rarity(5) == 0.3
        assert AnomalyService._calculate_digram_rarity(10) == 0.1


class TestCheckDuplicate:
    """Database test for duplicate detection."""

    def test_duplicate_receipt_id_is_detected(self, db_session):
        """
        TEST CASE: When a receipt ID already exists in the database,
        check_duplicate must return True with the original receipt's UUID.
        WHY: Exact duplicate receipt IDs indicate the same physical receipt
        being submitted twice — the strongest Layer 4 fraud signal.
        """
        existing_ocr = ReceiptOCR(
            receipt_id="existing-uuid-1",
            extracted_receipt_id="324-19204-128165",
            layer3_risk_score=0.0,
        )
        db_session.add(existing_ocr)
        db_session.commit()

        is_dup, original_id = AnomalyService.check_duplicate(
            db_session, "324-19204-128165", current_receipt_uuid="new-uuid-2"
        )
        assert is_dup is True
        assert original_id == "existing-uuid-1"

    def test_new_receipt_id_is_not_duplicate(self, db_session):
        """
        TEST CASE: When a receipt ID does not exist in the database,
        check_duplicate must return False.
        WHY: A new receipt ID should not be falsely flagged as a duplicate.
        """
        is_dup, original_id = AnomalyService.check_duplicate(
            db_session, "999-99999-999999", current_receipt_uuid="new-uuid"
        )
        assert is_dup is False
        assert original_id is None

    def test_same_receipt_does_not_self_match(self, db_session):
        """
        TEST CASE: A receipt must not be flagged as a duplicate of itself.
        WHY: When re-analyzing an existing receipt, the duplicate check must
        exclude the receipt being analyzed to avoid false positives.
        """
        existing_ocr = ReceiptOCR(
            receipt_id="same-uuid",
            extracted_receipt_id="324-19204-128165",
            layer3_risk_score=0.0,
        )
        db_session.add(existing_ocr)
        db_session.commit()

        is_dup, original_id = AnomalyService.check_duplicate(
            db_session, "324-19204-128165", current_receipt_uuid="same-uuid"
        )
        assert is_dup is False




def _create_test_receipt_ocr(db, receipt_uuid: str, receipt_id_value: str, student_id: int = 1):
    """Helper: create a full receipt chain (user → student → request → receipt → ocr)."""
    # Create user/student if not exists
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        user = User(email=f"s{student_id}@test.com", passwd="hash", role=UserRole.STUDENT)
        db.add(user)
        db.flush()
        student = Student(user_id=user.account_id, email=f"s{student_id}@test.com", name=f"S{student_id}")
        db.add(student)
        db.flush()
    
    request = Request(student_id=student.student_id, status=RequestStatus.PENDING, confirmed=False)
    db.add(request)
    db.flush()
    
    receipt = Receipt(
        receipt_id=receipt_uuid,
        student_id=student.student_id,
        request_id=request.request_id,
        file_path=f"uploads/test/{receipt_uuid}.jpg",
        sha256_hash=f"hash_{receipt_uuid}",
    )
    db.add(receipt)
    
    ocr = ReceiptOCR(
        receipt_id=receipt_uuid,
        extracted_receipt_id=receipt_id_value,
        layer3_risk_score=0.0,
        created_at=datetime.utcnow(),
    )
    db.add(ocr)
    
    # Also create anomaly record with initial risk 0.8 (solo pattern)
    anomaly = ReceiptAnomalies(
        receipt_id=receipt_uuid,
        receipt_id_length_anomaly=False,
        prefix_rarity_score=1.0,
        digram_rarity_score=1.0,
        layer4_risk_score=0.8,
    )
    db.add(anomaly)
    
    # Create risk assessment so retroactive update has something to update
    risk = ReceiptRiskAssessment(
        receipt_id=receipt_uuid,
        total_risk_score=0.8,
        assessment="high_risk",
        layer1_risk=0.0,
        layer2_risk=0.1,
        layer3_risk=0.0,
        layer4_risk=0.8,
        risk_factors={"layer4_anomaly": {"risk": 0.8}},
    )
    db.add(risk)
    db.commit()
    return receipt_uuid


class TestFindSimilarPatterns:
    """Tests for finding similar receipt patterns in the database."""

    def test_same_structure_and_stand_indicator_match(self, db_session):
        """
        TEST CASE: Two receipts with the same structure pattern (3-5-6)
        and the same stand indicator (first 2 digits of prefix) must be
        flagged as similar.
        WHY: Receipts from the same STPT stand/machine share these
        characteristics — this is the primary similarity signal.
        """
        # Existing receipt in database
        _create_test_receipt_ocr(db_session, "uuid-1", "324-19204-128165")

        # Now analyze a new receipt with similar pattern
        new_structure = AnomalyService.analyze_structure("324-19205-128200")
        similar = AnomalyService.find_similar_patterns(
            db_session, new_structure, exclude_receipt_id="uuid-new"
        )
        assert len(similar) == 1
        assert similar[0]["receipt_id"] == "uuid-1"

    def test_different_stand_indicator_not_similar(self, db_session):
        """
        TEST CASE: Two receipts with the same structure but different stand
        indicators (different first 2 digits) should not be flagged as similar
        based on structure alone — but may still match via n-gram overlap.
        WHY: Different stand indicators suggest different physical machines
        or different vendors. The structure pattern alone is not enough.
        """
        _create_test_receipt_ocr(db_session, "uuid-1", "999-88888-777777")

        new_structure = AnomalyService.analyze_structure("324-19204-128165")
        similar = AnomalyService.find_similar_patterns(
            db_session, new_structure, exclude_receipt_id="uuid-new"
        )
        # No similarity — different stand AND no significant digram overlap
        assert len(similar) == 0

    def test_excluded_receipt_is_not_returned(self, db_session):
        """
        TEST CASE: When exclude_receipt_id is provided, that receipt must
        not appear in the similar patterns list.
        WHY: When re-analyzing an existing receipt, we don't want it to
        match against itself and skew the risk score.
        """
        _create_test_receipt_ocr(db_session, "uuid-1", "324-19204-128165")

        new_structure = AnomalyService.analyze_structure("324-19205-128200")
        similar = AnomalyService.find_similar_patterns(
            db_session, new_structure, exclude_receipt_id="uuid-1"
        )
        assert len(similar) == 0

    def test_digram_overlap_triggers_similarity(self, db_session):
        """
        TEST CASE: Two receipts with high digram overlap (>=60%) should be
        flagged as similar even if structure or stand indicator differs.
        WHY: This is what gives Layer 4 tolerance to OCR errors. If OCR
        misreads one digit, the 2-gram overlap is still very high so the
        receipt clusters correctly with structurally similar ones.
        """
        # Original receipt
        _create_test_receipt_ocr(db_session, "uuid-1", "324-19204-128165")

        # OCR-corrupted version (extra leading digit) — should still match via digrams
        new_structure = AnomalyService.analyze_structure("1324-19204-128165")
        # Note: this has different structure (4-5-6 vs 3-5-6) but high digram overlap
        if new_structure["valid_format"]:
            similar = AnomalyService.find_similar_patterns(
                db_session, new_structure, exclude_receipt_id="uuid-new"
            )
            # High digram overlap should match
            assert len(similar) == 1


class TestRetroactiveRiskUpdate:
    """Tests for the retroactive risk score reduction — Layer 4's core feature."""

    def test_pair_pattern_reduces_solo_to_pair_risk(self, db_session):
        """
        TEST CASE: When a new receipt validates an existing solo pattern,
        the old receipt's risk must be retroactively reduced from 0.8 (solo)
        to 0.6 (pair).
        WHY: This is the central design feature of Layer 4 — risk scores
        are not final, they update as more evidence accumulates. The first
        receipt of a new pattern starts at high risk but should drop as
        similar receipts validate the pattern.
        """
        _create_test_receipt_ocr(db_session, "uuid-old", "324-19204-128165")

        # Verify initial state
        old_anomaly = db_session.query(ReceiptAnomalies).filter(
            ReceiptAnomalies.receipt_id == "uuid-old"
        ).first()
        assert old_anomaly.layer4_risk_score == 0.8

        # Simulate a new similar receipt being added — call retroactive update
        similar_receipts = [{"receipt_id": "uuid-old"}]
        AnomalyService.retroactive_risk_update(db_session, similar_receipts)

        # Check that old receipt's risk dropped to pair
        db_session.refresh(old_anomaly)
        assert old_anomaly.layer4_risk_score == 0.6

    def test_triplet_pattern_reduces_to_triplet_risk(self, db_session):
        """
        TEST CASE: When two new receipts validate a pattern, all old
        receipts must be updated to triplet risk (0.4).
        WHY: As cluster size grows, validation strengthens and risk
        should drop further to reflect this.
        """
        _create_test_receipt_ocr(db_session, "uuid-1", "324-19204-128165")
        _create_test_receipt_ocr(db_session, "uuid-2", "324-19205-128200", student_id=2)

        # Simulate a third receipt — cluster_size will be 3 (triplet)
        similar_receipts = [{"receipt_id": "uuid-1"}, {"receipt_id": "uuid-2"}]
        AnomalyService.retroactive_risk_update(db_session, similar_receipts)

        anomaly_1 = db_session.query(ReceiptAnomalies).filter(
            ReceiptAnomalies.receipt_id == "uuid-1"
        ).first()
        anomaly_2 = db_session.query(ReceiptAnomalies).filter(
            ReceiptAnomalies.receipt_id == "uuid-2"
        ).first()
        assert anomaly_1.layer4_risk_score == 0.4
        assert anomaly_2.layer4_risk_score == 0.4

    def test_validated_cluster_reduces_to_lowest_risk(self, db_session):
        """
        TEST CASE: When 3 or more receipts validate a pattern, all old
        receipts must drop to the validated cluster risk (0.2).
        WHY: A pattern shared by many receipts is well-established as
        legitimate, so risk should be minimal.
        """
        _create_test_receipt_ocr(db_session, "uuid-1", "324-19204-128165")
        _create_test_receipt_ocr(db_session, "uuid-2", "324-19205-128200", student_id=2)
        _create_test_receipt_ocr(db_session, "uuid-3", "324-19206-128300", student_id=3)

        # Simulate a fourth receipt arriving — cluster_size becomes 4
        similar_receipts = [
            {"receipt_id": "uuid-1"},
            {"receipt_id": "uuid-2"},
            {"receipt_id": "uuid-3"},
        ]
        AnomalyService.retroactive_risk_update(db_session, similar_receipts)

        for uid in ["uuid-1", "uuid-2", "uuid-3"]:
            anomaly = db_session.query(ReceiptAnomalies).filter(
                ReceiptAnomalies.receipt_id == uid
            ).first()
            assert anomaly.layer4_risk_score == 0.2

    def test_risk_only_decreases_never_increases(self, db_session):
        """
        TEST CASE: If an old receipt already has a lower risk than the
        new calculated risk, it must not be updated upward.
        WHY: The retroactive update is meant to validate patterns, not
        invalidate them. If a receipt is already in a validated cluster,
        a new similar receipt shouldn't push its risk back up.
        """
        _create_test_receipt_ocr(db_session, "uuid-old", "324-19204-128165")

        # Manually set old risk to a low value (simulate already-validated)
        old_anomaly = db_session.query(ReceiptAnomalies).filter(
            ReceiptAnomalies.receipt_id == "uuid-old"
        ).first()
        old_anomaly.layer4_risk_score = 0.2
        db_session.commit()

        # Call retroactive update with cluster size 2 (would give risk 0.6)
        similar_receipts = [{"receipt_id": "uuid-old"}]
        AnomalyService.retroactive_risk_update(db_session, similar_receipts)

        # Risk should NOT have been raised
        db_session.refresh(old_anomaly)
        assert old_anomaly.layer4_risk_score == 0.2

    def test_final_risk_assessment_also_updated(self, db_session):
        """
        TEST CASE: When Layer 4 risk drops retroactively, the total risk
        assessment for the receipt must also be recalculated.
        WHY: Without this, the admin would see an outdated total risk score
        that doesn't reflect the updated layer 4 evidence — the retroactive
        update would be invisible at the assessment level.
        """
        _create_test_receipt_ocr(db_session, "uuid-old", "324-19204-128165")

        # Verify initial total risk assessment
        old_assessment = db_session.query(ReceiptRiskAssessment).filter(
            ReceiptRiskAssessment.receipt_id == "uuid-old"
        ).first()
        initial_total = old_assessment.total_risk_score

        # Simulate validation
        similar_receipts = [{"receipt_id": "uuid-old"}]
        AnomalyService.retroactive_risk_update(db_session, similar_receipts)

        # Total risk assessment should also drop
        db_session.refresh(old_assessment)
        assert old_assessment.layer4_risk == 0.6
        # Total risk should have decreased since layer4 weight is 10% of total
        assert old_assessment.total_risk_score < initial_total     