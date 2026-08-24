import time
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.db.session import get_db
from app.deps import get_current_user_optional
from app.ml.inference import predict_url
from app.schemas.predict import URLPredictRequest, PredictResponse
from app.api.scan_store import persist_scan

router = APIRouter(prefix="/api/v1/predict", tags=["predict"])


def _validate_url(raw: str) -> str:
    candidate = raw if "://" in raw else f"http://{raw}"
    parts = urlsplit(candidate)
    if not parts.hostname or "." not in parts.hostname and parts.hostname != "localhost":
        raise HTTPException(status_code=422, detail="Malformed URL: could not determine a valid hostname")
    if parts.scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail="Only http/https URLs are supported")
    return raw


@router.post("/url", response_model=PredictResponse)
@limiter.limit("60/minute")
def predict_url_endpoint(
    request: Request,
    payload: URLPredictRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    url = _validate_url(payload.url)
    start = time.perf_counter()
    result = predict_url(url)
    latency_ms = (time.perf_counter() - start) * 1000

    scan = persist_scan(db, user_id=user.id if user else None, input_type="url", input_raw=url, result=result)

    return PredictResponse(scan_id=scan.id, latency_ms=latency_ms, **result)
