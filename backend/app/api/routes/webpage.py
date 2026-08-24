import time
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.deps import get_current_user_optional
from app.ml.inference import predict_webpage
from app.schemas.predict import WebpagePredictRequest, PredictResponse
from app.api.scan_store import persist_scan

router = APIRouter(prefix="/api/v1/predict", tags=["predict"])


@router.post("/webpage", response_model=PredictResponse)
@limiter.limit("30/minute")
def predict_webpage_endpoint(
    request: Request,
    payload: WebpagePredictRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    candidate = payload.url if "://" in payload.url else f"http://{payload.url}"
    parts = urlsplit(candidate)
    if not parts.hostname:
        raise HTTPException(status_code=422, detail="Malformed URL: could not determine a valid hostname")

    start = time.perf_counter()
    result = predict_webpage(payload.url, use_network=settings.webpage_fetch_use_network)
    latency_ms = (time.perf_counter() - start) * 1000

    scan = persist_scan(db, user_id=user.id if user else None, input_type="webpage", input_raw=payload.url, result=result)

    return PredictResponse(scan_id=scan.id, latency_ms=latency_ms, **result)
