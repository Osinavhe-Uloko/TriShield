from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class URLPredictRequest(BaseModel):
    url: str = Field(..., min_length=3, max_length=2048)

    @field_validator("url")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("url must not be empty")
        return v


class EmailPredictRequest(BaseModel):
    raw_email: str | None = None
    headers: dict[str, str] | None = None
    body: str | None = None

    @field_validator("raw_email")
    @classmethod
    def require_content(cls, v, info):
        return v


class WebpagePredictRequest(BaseModel):
    url: str = Field(..., min_length=3, max_length=2048)


class PredictResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    scan_id: str
    verdict: str
    confidence: float
    risk_score: float
    reasons: list[str]
    feature_breakdown: dict
    channel_breakdown: dict | None = None
    model_version: str
    latency_ms: float


class FeedbackRequest(BaseModel):
    scan_id: str
    user_verdict: str = Field(..., pattern="^(phishing|legitimate)$")


class ScanHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: str
    input_type: str
    input_raw: str
    verdict: str
    confidence: float
    risk_score: float
    model_version: str
    created_at: datetime


class AnalyticsSummary(BaseModel):
    total_scans: int
    phishing_count: int
    legitimate_count: int
    by_channel: dict[str, int]
    average_confidence: float
    feedback_accuracy: float | None
    scans_last_7_days: dict[str, int]


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
