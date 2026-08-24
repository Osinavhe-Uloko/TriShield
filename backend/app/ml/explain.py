"""Explainability: turns a model's SHAP feature attributions into
human-readable reason strings, e.g. "domain registered recently" rather
than a raw feature name + coefficient."""
from __future__ import annotations

import numpy as np
import shap

TOP_K_REASONS = 5

# feature_name -> function(raw_value) -> human-readable phrase, or None
# if this particular value isn't worth surfacing as a reason.
URL_REASON_TEMPLATES = {
    "has_ip_address": lambda v: "URL uses a raw IP address instead of a domain name" if v else None,
    "has_https": lambda v: "connection is not encrypted (no HTTPS)" if not v else None,
    "is_shortener": lambda v: "URL uses a link-shortening service, hiding the real destination" if v else None,
    "suspicious_keyword_count": lambda v: f"contains {int(v)} suspicious keyword(s) (e.g. 'login', 'verify', 'secure')" if v >= 1 else None,
    "tld_is_suspicious": lambda v: "uses a top-level domain commonly abused for phishing" if v else None,
    "brand_edit_distance_min": lambda v: "domain name closely resembles a well-known brand (possible typosquatting)" if v <= 2 else None,
    "num_subdomains": lambda v: f"unusually deep subdomain nesting ({int(v)} levels)" if v >= 3 else None,
    "domain_entropy": lambda v: "domain name looks randomly generated" if v >= 4.0 else None,
    "num_at": lambda v: "URL contains an '@' symbol, which can hide the true destination" if v >= 1 else None,
    "has_double_slash_redirect": lambda v: "URL path contains a suspicious redirect pattern ('//')" if v else None,
    "url_length": lambda v: "unusually long URL" if v >= 100 else None,
    "domain_age_days": lambda v: f"domain was registered only {int(v)} day(s) ago" if 0 <= v < 30 else None,
    "count_special_chars": lambda v: "URL contains many unusual special characters" if v >= 3 else None,
    "char_repetition_max": lambda v: "URL contains long repeated character sequences" if v >= 5 else None,
}

EMAIL_REASON_TEMPLATES = {
    "sender_replyto_mismatch": lambda v: "the Reply-To address does not match the sender's domain" if v else None,
    "display_name_addr_mismatch": lambda v: "sender display name impersonates a known brand but the address doesn't match" if v else None,
    "num_urgency_phrases": lambda v: f"contains {int(v)} urgency/pressure phrase(s) (e.g. 'act now', 'account suspended')" if v >= 1 else None,
    "spf_fail": lambda v: "SPF authentication failed" if v else None,
    "dkim_fail": lambda v: "DKIM authentication failed" if v else None,
    "dmarc_fail": lambda v: "DMARC authentication failed" if v else None,
    "num_ip_urls": lambda v: "email links to a raw IP address" if v >= 1 else None,
    "anchor_href_text_mismatch": lambda v: "link text doesn't match its actual destination" if v >= 1 else None,
    "num_suspicious_tld_links": lambda v: "email links to a domain with a high-risk top-level domain" if v >= 1 else None,
    "subject_has_urgency": lambda v: "subject line uses urgency/pressure language" if v else None,
}

WEB_REASON_TEMPLATES = {
    "using_ip": lambda v: "page is hosted at a raw IP address" if v == -1 else None,
    "https_valid": lambda v: "page does not use a valid HTTPS certificate" if v <= 0 else None,
    "prefix_suffix": lambda v: "domain name contains a hyphen (common in impersonation domains)" if v == -1 else None,
    "favicon_external": lambda v: "page favicon is loaded from a different domain than the page itself" if v == -1 else None,
    "iframe_present": lambda v: "page contains hidden iframes" if v == -1 else None,
    "server_form_handler": lambda v: "login/data form submits to a different or blank domain" if v <= 0 else None,
    "request_url_external_pct": lambda v: "most page resources (images/scripts) load from external domains" if v == -1 else None,
    "anchor_url_external_pct": lambda v: "most links on the page point off-site or nowhere" if v == -1 else None,
    "disable_right_click": lambda v: "page disables right-click, a common evasion trick" if v == -1 else None,
    "using_popup_window": lambda v: "page uses popups/prompts, often used to harvest credentials" if v == -1 else None,
    "domain_age_ok": lambda v: "domain appears to be very recently registered" if v == -1 else None,
    "blacklist_pattern_match": lambda v: "hostname matches a known suspicious pattern" if v == -1 else None,
    "sub_domains": lambda v: "unusually deep subdomain structure" if v == -1 else None,
    "short_url": lambda v: "URL uses a link-shortening service" if v == -1 else None,
}

_TEMPLATES_BY_CHANNEL = {
    "url": URL_REASON_TEMPLATES,
    "email": EMAIL_REASON_TEMPLATES,
    "web": WEB_REASON_TEMPLATES,
}

_explainer_cache: dict[int, shap.TreeExplainer] = {}


def _get_explainer(model) -> shap.TreeExplainer:
    key = id(model)
    if key not in _explainer_cache:
        _explainer_cache[key] = shap.TreeExplainer(model)
    return _explainer_cache[key]


def explain_prediction(
    channel: str,
    model,
    feature_dict: dict,
    feature_names: list[str],
    x_override: np.ndarray | None = None,
) -> list[dict]:
    """Returns a list of {reason, shap_value, feature} dicts, most
    important first, for features that pushed the prediction toward
    "phishing". Falls back to template-only heuristics (no SHAP) if the
    model isn't a supported tree model.

    ``x_override``/``feature_names`` support models fed a wider vector
    than the human-readable features alone (e.g. the email model also
    takes TF-IDF token columns): pass the full model-input vector as
    ``x_override`` with its matching (longer) ``feature_names``, while
    ``feature_dict`` stays the small raw-valued dict used to render each
    template's phrase. Columns with no template (e.g. TF-IDF tokens)
    are ranked but silently skipped when rendering reasons.
    """
    templates = _TEMPLATES_BY_CHANNEL.get(channel, {})
    x = x_override if x_override is not None else np.array([[feature_dict[f] for f in feature_names]], dtype=float)

    try:
        explainer = _get_explainer(model)
        shap_values = explainer.shap_values(x)
        if isinstance(shap_values, list):  # binary classifier returning [class0, class1]
            shap_values = shap_values[1]
        contributions = shap_values[0]
    except Exception:
        importances = getattr(model, "feature_importances_", np.ones(len(feature_names)))
        contributions = importances

    ranked = sorted(
        zip(feature_names, contributions),
        key=lambda t: abs(t[1]),
        reverse=True,
    )

    reasons = []
    for feature_name, contribution in ranked:
        if contribution <= 0:
            continue  # only surface features pushing toward "phishing"
        template = templates.get(feature_name)
        if not template or feature_name not in feature_dict:
            continue
        phrase = template(feature_dict[feature_name])
        if not phrase:
            continue
        reasons.append({
            "feature": feature_name,
            "reason": phrase,
            "importance": round(float(contribution), 4),
        })
        if len(reasons) >= TOP_K_REASONS:
            break

    if not reasons:
        reasons.append({
            "feature": None,
            "reason": "no single dominant risk indicator; verdict is based on the combined feature profile",
            "importance": 0.0,
        })
    return reasons
