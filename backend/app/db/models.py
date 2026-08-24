import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Text, JSON, Integer
from sqlalchemy.orm import relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    scans = relationship("Scan", back_populates="user")


class Scan(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    input_type = Column(String, nullable=False)  # url | email | webpage
    input_raw = Column(Text, nullable=False)
    verdict = Column(String, nullable=False)  # phishing | legitimate
    confidence = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    reasons = Column(JSON, default=list)
    model_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow, index=True)

    user = relationship("User", back_populates="scans")
    features = relationship("ScanFeature", back_populates="scan", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="scan", cascade="all, delete-orphan")


class ScanFeature(Base):
    __tablename__ = "scan_features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False, index=True)
    feature_name = Column(String, nullable=False)
    feature_value = Column(Float, nullable=True)

    scan = relationship("Scan", back_populates="features")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(String, primary_key=True, default=_uuid)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False, index=True)
    user_verdict = Column(String, nullable=False)  # phishing | legitimate
    submitted_at = Column(DateTime, default=_utcnow)

    scan = relationship("Scan", back_populates="feedback")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String, nullable=False)  # url | email | web
    version = Column(String, nullable=False)
    trained_at = Column(DateTime, default=_utcnow)
    metrics_json = Column(JSON, default=dict)
