from sqlalchemy.orm import Session

from app.db.models import Scan, ScanFeature


def persist_scan(
    db: Session,
    *,
    user_id: str | None,
    input_type: str,
    input_raw: str,
    result: dict,
) -> Scan:
    scan = Scan(
        user_id=user_id,
        input_type=input_type,
        input_raw=input_raw[:5000],
        verdict=result["verdict"],
        confidence=result["confidence"],
        risk_score=result["risk_score"],
        reasons=result["reasons"],
        model_version=result["model_version"],
    )
    db.add(scan)
    db.flush()

    for name, value in result.get("feature_breakdown", {}).items():
        try:
            db.add(ScanFeature(scan_id=scan.id, feature_name=name, feature_value=float(value)))
        except (TypeError, ValueError):
            continue

    db.commit()
    db.refresh(scan)
    return scan
