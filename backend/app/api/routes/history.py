from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Scan
from app.deps import get_current_user_optional
from app.schemas.predict import ScanHistoryItem

router = APIRouter(prefix="/api/v1", tags=["history"])


@router.get("/history", response_model=list[ScanHistoryItem])
def get_history(
    user_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    effective_user_id = user_id or (user.id if user else None)
    query = db.query(Scan).order_by(Scan.created_at.desc())
    if effective_user_id:
        query = query.filter(Scan.user_id == effective_user_id)
    return query.limit(limit).all()
