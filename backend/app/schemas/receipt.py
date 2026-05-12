# app/schemas/receipt.py
from pydantic import BaseModel
from typing import Optional


class Layer1Result(BaseModel):
    fraud_detected: bool
    duplicate_detected: bool
    risk: float


class Layer2Result(BaseModel):
    has_editing_software: bool
    editing_software: Optional[str] = None
    flags: list[str] = []
    risk: float


class Layer3Result(BaseModel):
    stpt_id_matches: Optional[bool] = None
    extracted_stpt_id: Optional[str] = None
    expected_stpt_id: Optional[str] = None
    flags: list[str] = []
    risk: float


class Layer4Result(BaseModel):
    risk: float


class RiskFactors(BaseModel):
    layer1_hash: Layer1Result
    layer2_exif: Layer2Result
    layer3_ocr: Layer3Result
    layer4_anomaly: Layer4Result
    total_risk: float
    assessment: str


class RiskAssessmentResponse(BaseModel):
    total_risk_score: float
    assessment: str
    layer1_risk: float
    layer2_risk: float
    layer3_risk: float
    layer4_risk: float
    risk_factors: RiskFactors


class ReceiptResponse(BaseModel):
    receipt_id: str
    file_path: str
    sha256_hash: str
    risk_assessment: Optional[RiskAssessmentResponse] = None


class ReceiptSubmitResponse(BaseModel):
    action: str
    message: str
    receipt_id: Optional[str] = None
    student_id: int
    final_assessment: Optional[RiskAssessmentResponse] = None
