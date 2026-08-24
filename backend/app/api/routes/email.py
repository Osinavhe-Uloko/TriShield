import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.db.session import get_db
from app.deps import get_current_user_optional
from app.ml.inference import predict_email
from app.schemas.predict import EmailPredictRequest, PredictResponse
from app.api.scan_store import persist_scan

router = APIRouter(prefix="/api/v1/predict", tags=["predict"])


@router.post("/email", response_model=PredictResponse)
@limiter.limit("60/minute")
def predict_email_endpoint(
    request: Request,
    payload: EmailPredictRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    if not payload.raw_email and not payload.body:
        raise HTTPException(status_code=422, detail="Provide either raw_email or headers+body")

    start = time.perf_counter()
    result = predict_email(
        raw_email=payload.raw_email or "",
        headers=payload.headers,
        body=payload.body or "",
    )
    latency_ms = (time.perf_counter() - start) * 1000

    raw_for_storage = payload.raw_email or payload.body or ""
    scan = persist_scan(db, user_id=user.id if user else None, input_type="email", input_raw=raw_for_storage, result=result)

    return PredictResponse(scan_id=scan.id, latency_ms=latency_ms, **result)
