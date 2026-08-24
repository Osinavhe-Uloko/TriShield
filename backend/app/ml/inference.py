"""Loads trained model artifacts once at startup and exposes the three
per-channel prediction functions used by the API routes."""
from __future__ import annotations

import re
from pathlib import Path

import joblib
import numpy as np
import scipy.sparse as sp

from app.ml.features import (
    extract_url_features, URL_FEATURE_NAMES,
    extract_email_features, EMAIL_FEATURE_NAMES,
    extract_web_features, WEB_FEATURE_NAMES,
)
from app.ml.fusion import ChannelScore, fuse_scores, verdict_from_score, confidence_from_score
from app.ml.explain import explain_prediction

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

_url_model = joblib.load(ARTIFACTS_DIR / "url_model.joblib")
_email_model = joblib.load(ARTIFACTS_DIR / "email_model.joblib")
_email_vectorizer = joblib.load(ARTIFACTS_DIR / "email_tfidf_vectorizer.joblib")
_email_scaler = joblib.load(ARTIFACTS_DIR / "email_scaler.joblib")
_email_feature_names = list(_email_vectorizer.get_feature_names_out()) + EMAIL_FEATURE_NAMES
_web_model = joblib.load(ARTIFACTS_DIR / "web_model.joblib")

MODEL_VERSION = "1.0.0"


def _url_risk_score(url: str, use_network: bool = False) -> tuple[float, dict]:
    feats = extract_url_features(url, use_network=use_network)
    x = np.array([[feats[f] for f in URL_FEATURE_NAMES]], dtype=float)
    score = float(_url_model.predict_proba(x)[0, 1])
    return score, feats


def _email_risk_score(raw_email: str = "", headers: dict | None = None, body: str = "") -> tuple[float, dict, str, np.ndarray]:
    feats = extract_email_features(raw_email=raw_email, headers=headers, body=body)
    text = f"{(headers or {}).get('Subject', '')}\n{body or raw_email}"
    text_matrix = _email_vectorizer.transform([text])
    struct = _email_scaler.transform(np.array([[feats[f] for f in EMAIL_FEATURE_NAMES]], dtype=float))
    x_sparse = sp.hstack([text_matrix, sp.csr_matrix(struct)]).tocsr()
    score = float(_email_model.predict_proba(x_sparse)[0, 1])
    x_dense = x_sparse.toarray()
    return score, feats, body or raw_email, x_dense


def _web_risk_score(url: str, html: str | None = None, use_network: bool = True) -> tuple[float, dict]:
    feats = extract_web_features(url, html=html, use_network=use_network)
    x = np.array([[feats[f] for f in WEB_FEATURE_NAMES]], dtype=float)
    score = float(_web_model.predict_proba(x)[0, 1])
    return score, feats


def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s\"'<>\)]+", text or "")


def predict_url(url: str, use_network: bool = False) -> dict:
    score, feats = _url_risk_score(url, use_network=use_network)
    reasons = explain_prediction("url", _url_model, feats, URL_FEATURE_NAMES)
    return {
        "verdict": verdict_from_score(score),
        "confidence": confidence_from_score(score),
        "risk_score": score,
        "reasons": [r["reason"] for r in reasons],
        "feature_breakdown": feats,
        "model_version": MODEL_VERSION,
    }


def predict_email(raw_email: str = "", headers: dict | None = None, body: str = "") -> dict:
    email_score, feats, full_body, x_dense = _email_risk_score(raw_email, headers, body)
    email_reasons = explain_prediction(
        "email", _email_model, feats, _email_feature_names, x_override=x_dense
    )

    channel_scores = [ChannelScore("email_content", email_score, weight=0.7)]
    url_reasons: list[dict] = []
    for link in _extract_urls(full_body)[:5]:
        link_score, link_feats = _url_risk_score(link, use_network=False)
        channel_scores.append(ChannelScore(f"embedded_url:{link}", link_score, weight=0.3 / max(len(_extract_urls(full_body)[:5]), 1)))
        if link_score >= 0.5:
            url_reasons.append({"reason": f"embedded link looks suspicious: {link}", "importance": link_score})

    final_score = fuse_scores(channel_scores)
    reasons = [r["reason"] for r in email_reasons] + [r["reason"] for r in url_reasons]

    return {
        "verdict": verdict_from_score(final_score),
        "confidence": confidence_from_score(final_score),
        "risk_score": final_score,
        "reasons": reasons[:8],
        "feature_breakdown": feats,
        "channel_breakdown": {"email_content_score": email_score, "embedded_url_scores": [c.risk_score for c in channel_scores[1:]]},
        "model_version": MODEL_VERSION,
    }


def predict_webpage(url: str, use_network: bool = True) -> dict:
    url_score, url_feats = _url_risk_score(url, use_network=False)
    web_score, web_feats = _web_risk_score(url, use_network=use_network)

    channel_scores = [
        ChannelScore("web_content", web_score, weight=0.6),
        ChannelScore("url_structure", url_score, weight=0.4),
    ]
    final_score = fuse_scores(channel_scores)

    web_reasons = explain_prediction("web", _web_model, web_feats, WEB_FEATURE_NAMES)
    url_reasons = explain_prediction("url", _url_model, url_feats, URL_FEATURE_NAMES)
    reasons = [r["reason"] for r in web_reasons] + [r["reason"] for r in url_reasons[:2]]

    return {
        "verdict": verdict_from_score(final_score),
        "confidence": confidence_from_score(final_score),
        "risk_score": final_score,
        "reasons": reasons[:8],
        "feature_breakdown": {**web_feats, **{f"url_{k}": v for k, v in url_feats.items()}},
        "channel_breakdown": {"web_content_score": web_score, "url_structure_score": url_score},
        "model_version": MODEL_VERSION,
    }
