from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Scan, Feedback
from app.schemas.predict import AnalyticsSummary

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def analytics_summary(db: Session = Depends(get_db)):
    total_scans = db.query(func.count(Scan.id)).scalar() or 0
    phishing_count = db.query(func.count(Scan.id)).filter(Scan.verdict == "phishing").scalar() or 0
    legitimate_count = total_scans - phishing_count

    by_channel = dict(
        db.query(Scan.input_type, func.count(Scan.id)).group_by(Scan.input_type).all()
    )
    average_confidence = db.query(func.avg(Scan.confidence)).scalar() or 0.0

    correct = (
        db.query(func.count(Feedback.id))
        .join(Scan, Feedback.scan_id == Scan.id)
        .filter(Feedback.user_verdict == Scan.verdict)
        .scalar()
        or 0
    )
    total_feedback = db.query(func.count(Feedback.id)).scalar() or 0
    feedback_accuracy = (correct / total_feedback) if total_feedback else None

    since = datetime.now(timezone.utc) - timedelta(days=7)
    recent = db.query(Scan.created_at).filter(Scan.created_at >= since).all()
    by_day: dict[str, int] = defaultdict(int)
    for (created_at,) in recent:
        by_day[created_at.strftime("%Y-%m-%d")] += 1

    return AnalyticsSummary(
        total_scans=total_scans,
        phishing_count=phishing_count,
        legitimate_count=legitimate_count,
        by_channel=by_channel,
        average_confidence=float(average_confidence),
        feedback_accuracy=feedback_accuracy,
        scans_last_7_days=dict(by_day),
    )
