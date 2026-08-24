"""Cross-channel signal fusion.

The three public endpoints (/predict/url, /predict/email,
/predict/webpage) each answer a different question, so there is no
single shared "fuse all three" call. Instead, fusion happens *within* a
request whenever it naturally spans channels:

  - Scanning an email also runs the URL model against every embedded
    link (a legitimate-looking email with a phishing link should still
    be flagged).
  - Scanning a webpage also runs the URL model against the page's own
    URL (lexical tricks in the address bar matter alongside the DOM).

This is a weighted rule-based combiner rather than a trained
meta-learner (spec section 8, option (a)): the three training datasets
come from disjoint sources with no shared ground-truth incidents to fit
a stacking classifier on. The interface is kept generic
(``fuse_scores``) so a meta-learner trained on real joint-labelled
incident data can be dropped in later without changing callers.
"""
from dataclasses import dataclass


@dataclass
class ChannelScore:
    channel: str
    risk_score: float  # 0..1 probability of phishing
    weight: float


def fuse_scores(scores: list[ChannelScore]) -> float:
    """Weighted average of channel risk scores, renormalized over
    whichever channels actually produced a score for this request."""
    total_weight = sum(s.weight for s in scores)
    if total_weight == 0:
        return 0.0
    return sum(s.risk_score * s.weight for s in scores) / total_weight


def verdict_from_score(risk_score: float, threshold: float = 0.5) -> str:
    return "phishing" if risk_score >= threshold else "legitimate"


def confidence_from_score(risk_score: float) -> float:
    """Distance from the decision boundary, rescaled to 0.5-1.0."""
    return 0.5 + abs(risk_score - 0.5)
