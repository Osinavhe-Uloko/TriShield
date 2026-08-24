from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Scan, Feedback
from app.schemas.predict import FeedbackRequest

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/feedback", status_code=201)
def submit_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    scan = db.query(Scan).filter(Scan.id == payload.scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    feedback = Feedback(scan_id=scan.id, user_verdict=payload.user_verdict)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"id": feedback.id, "scan_id": feedback.scan_id, "user_verdict": feedback.user_verdict}
