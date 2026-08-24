"""Feature extraction for email content + headers.

Two extraction paths feed the model:
  1. Structured heuristic features (this module) -> numeric vector.
  2. Raw subject+body text -> TF-IDF vector (built by the training
     pipeline / loaded vectorizer at inference time).

The final email model concatenates both, matching the spec's
"TF-IDF + LightGBM" design (section 8) while still surfacing
human-readable heuristic reasons for explainability.
"""
from __future__ import annotations

import re
from email import message_from_string
from email.utils import parseaddr

URGENCY_PHRASES = [
    "act now", "verify your account", "account suspended", "urgent",
    "immediately", "click here", "confirm your", "will be closed",
    "unusual activity", "limited time", "password expires", "act today",
    "final notice", "as soon as possible", "security alert", "unauthorized",
    "restricted", "validate your", "update your billing", "winner",
    "congratulations", "claim your", "verify now", "suspended",
]

EMAIL_FEATURE_NAMES = [
    "num_urls", "num_ip_urls", "sender_replyto_mismatch",
    "display_name_addr_mismatch", "num_urgency_phrases", "has_attachment",
    "html_to_text_ratio", "num_exclamations", "subject_has_urgency",
    "anchor_href_text_mismatch", "spf_fail", "dkim_fail", "dmarc_fail",
    "body_length", "num_words", "uppercase_ratio", "num_suspicious_tld_links",
]


def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s\"'<>\)]+", text or "")


def _domain_of(addr: str) -> str:
    _, email_addr = parseaddr(addr or "")
    if "@" in email_addr:
        return email_addr.split("@")[-1].lower()
    return ""


def extract_email_features(raw_email: str = "", headers: dict | None = None, body: str = "") -> dict:
    """Extract heuristic phishing-signal features from an email.

    Accepts either a full raw RFC822 message (``raw_email``) or a
    pre-split ``headers`` dict + ``body`` string, so it works for both
    forwarded-email uploads and structured API submissions.
    """
    headers = dict(headers or {})
    if raw_email:
        try:
            msg = message_from_string(raw_email)
            for key in ("From", "To", "Reply-To", "Subject", "Received-SPF",
                        "Authentication-Results"):
                if key in msg and key not in headers:
                    headers[key] = msg.get(key, "")
            if not body:
                if msg.is_multipart():
                    parts = []
                    for part in msg.walk():
                        if part.get_content_type() in ("text/plain", "text/html"):
                            try:
                                parts.append(part.get_payload(decode=True).decode(errors="replace"))
                            except Exception:
                                pass
                    body = "\n".join(parts)
                else:
                    payload = msg.get_payload(decode=True)
                    body = payload.decode(errors="replace") if payload else msg.get_payload()
        except Exception:
            body = body or raw_email

    subject = headers.get("Subject", "")
    from_addr = headers.get("From", "")
    reply_to = headers.get("Reply-To", "")
    auth_results = (headers.get("Authentication-Results", "") or "").lower()

    full_text = f"{subject}\n{body}".lower()
    urls = _extract_urls(body)

    from_domain = _domain_of(from_addr)
    replyto_domain = _domain_of(reply_to)

    ip_url_count = sum(1 for u in urls if re.search(r"://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", u))

    anchor_mismatches = 0
    for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', body, re.IGNORECASE):
        href, text = match.group(1), match.group(2)
        href_urls = _extract_urls(href) or [href]
        text_urls = _extract_urls(text)
        if text_urls and href_urls and text_urls[0] != href_urls[0]:
            anchor_mismatches += 1

    html_tag_count = len(re.findall(r"<[a-zA-Z][^>]*>", body))
    words = re.findall(r"\w+", body)

    suspicious_tld_links = sum(
        1 for u in urls if re.search(r"\.(tk|ml|ga|cf|gq|xyz|top|click)(/|$)", u.lower())
    )

    features = {
        "num_urls": len(urls),
        "num_ip_urls": ip_url_count,
        "sender_replyto_mismatch": int(bool(replyto_domain) and replyto_domain != from_domain),
        "display_name_addr_mismatch": int(_display_name_mismatch(from_addr)),
        "num_urgency_phrases": sum(1 for p in URGENCY_PHRASES if p in full_text),
        "has_attachment": int("content-disposition: attachment" in (raw_email or "").lower()),
        "html_to_text_ratio": (html_tag_count / max(len(words), 1)),
        "num_exclamations": body.count("!") + subject.count("!"),
        "subject_has_urgency": int(any(p in subject.lower() for p in URGENCY_PHRASES)),
        "anchor_href_text_mismatch": anchor_mismatches,
        "spf_fail": int("spf=fail" in auth_results or "spf=softfail" in auth_results),
        "dkim_fail": int("dkim=fail" in auth_results),
        "dmarc_fail": int("dmarc=fail" in auth_results),
        "body_length": len(body),
        "num_words": len(words),
        "uppercase_ratio": (sum(1 for c in body if c.isupper()) / max(len(body), 1)),
        "num_suspicious_tld_links": suspicious_tld_links,
    }
    return features


def _display_name_mismatch(from_header: str) -> bool:
    display_name, addr = parseaddr(from_header or "")
    if not display_name or "@" not in addr:
        return False
    display_lower = display_name.lower()
    local_part = addr.split("@")[0].lower()
    looks_like_brand = any(
        brand in display_lower
        for brand in ["paypal", "bank", "amazon", "microsoft", "apple", "support", "security"]
    )
    return looks_like_brand and brand_not_in(local_part, display_lower)


def brand_not_in(local_part: str, display_lower: str) -> bool:
    for brand in ["paypal", "bank", "amazon", "microsoft", "apple"]:
        if brand in display_lower and brand not in local_part:
            return True
    return False
