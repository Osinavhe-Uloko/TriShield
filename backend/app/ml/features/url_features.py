"""Lexical + host-based feature extraction for URLs.

Design notes
------------
Every feature here is computed directly from the URL string with no
network I/O by default, so the same function can run at training time
over ~400k rows in seconds and at inference time within the <2s API
budget. Two host-based features (``domain_age_days``, ``has_mx_record``)
*can* use live WHOIS/DNS lookups when ``use_network=True``, but default
to a neutral "unknown" sentinel (-1) because:

  1. Training needs to run offline/deterministically over a large corpus.
  2. WHOIS (port 43) and recursive DNS are frequently unreachable from
     sandboxed/production egress-restricted environments, so a model
     that *requires* them is not robust. Tree models handle a
     "missing/unknown" sentinel category fine.

This keeps the extractor safe to add new indicators to later (append a
column, add it to ``URL_FEATURE_NAMES``, retrain) without touching the
serving code path.
"""
from __future__ import annotations

import ipaddress
import math
import re
import socket
from collections import Counter
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

try:
    import tldextract

    _TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())  # offline snapshot only
except Exception:  # pragma: no cover - tldextract always installed, defensive only
    _TLD_EXTRACTOR = None

SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "adf.ly", "bl.ink", "lnkd.in", "rebrand.ly", "cutt.ly", "shorte.st",
    "tiny.cc", "soo.gd", "s2r.co", "clck.ru", "v.gd", "qr.ae", "u.to",
}

SUSPICIOUS_KEYWORDS = [
    "login", "verify", "secure", "update", "banking", "account", "confirm",
    "signin", "sign-in", "webscr", "ebayisapi", "password", "wp-admin",
    "suspend", "urgent", "billing", "invoice", "unlock", "reset", "support",
    "security", "alert", "validate", "authenticate", "recover", "gift",
]

SUSPICIOUS_TLDS = {
    "tk", "ml", "ga", "cf", "gq", "xyz", "top", "work", "click", "link",
    "loan", "download", "review", "country", "kim", "science", "party",
    "gdn", "men", "racing", "win", "bid", "stream", "accountant",
}

POPULAR_BRAND_DOMAINS = [
    "google", "paypal", "microsoft", "apple", "amazon", "facebook",
    "instagram", "netflix", "bankofamerica", "chase", "wellsfargo",
    "dropbox", "linkedin", "twitter", "whatsapp", "outlook", "office365",
    "icloud", "yahoo", "ebay", "adobe", "coinbase", "binance",
]

URL_FEATURE_NAMES = [
    "url_length", "hostname_length", "path_length", "query_length",
    "num_dots", "num_hyphens", "num_underscores", "num_at", "num_percent",
    "num_digits", "num_params", "num_fragments", "digit_ratio",
    "has_ip_address", "has_https", "is_shortener", "num_subdomains",
    "suspicious_keyword_count", "domain_entropy", "url_entropy",
    "tld_is_suspicious", "brand_edit_distance_min", "has_port",
    "double_extension", "count_special_chars", "hostname_is_numeric_only",
    "num_slashes_in_path", "has_hex_encoding", "tld_length", "contains_www",
    "char_repetition_max", "has_double_slash_redirect", "domain_age_days",
    "has_mx_record",
]


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def _is_ip_host(hostname: str) -> bool:
    if not hostname:
        return False
    host = hostname.strip("[]")
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def _max_char_repetition(s: str) -> int:
    if not s:
        return 0
    best = cur = 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


@dataclass
class HostLookupResult:
    domain_age_days: int = -1
    has_mx_record: int = -1


def _lookup_host_info(hostname: str, timeout: float = 2.0) -> HostLookupResult:
    """Best-effort WHOIS/DNS lookup. Returns -1 sentinels on any failure
    (blocked egress, timeout, missing package) rather than raising, since
    these signals are optional enrichments, not hard requirements."""
    result = HostLookupResult()
    try:
        import whois  # python-whois

        socket.setdefaulttimeout(timeout)
        w = whois.whois(hostname)
        created = w.creation_date
        if isinstance(created, list):
            created = created[0] if created else None
        if created:
            import datetime

            age = (datetime.datetime.now() - created).days
            if age >= 0:
                result.domain_age_days = age
    except Exception:
        pass
    try:
        import dns.resolver

        socket.setdefaulttimeout(timeout)
        answers = dns.resolver.resolve(hostname, "MX", lifetime=timeout)
        result.has_mx_record = 1 if len(answers) > 0 else 0
    except Exception:
        pass
    return result


def extract_url_features(url: str, use_network: bool = False) -> dict:
    """Extract the lexical (+ optional host-based) feature vector for a URL.

    Parameters
    ----------
    url: raw URL string (scheme optional; ``example.com/x`` is normalized
        to ``http://example.com/x`` before parsing).
    use_network: when True, attempts a best-effort WHOIS/DNS lookup for
        the host-based features. Off by default (see module docstring).
    """
    raw = url.strip()
    if "://" not in raw:
        raw = "http://" + raw

    parts = urlsplit(raw)
    hostname = (parts.hostname or "").lower()
    path = parts.path or ""
    query = parts.query or ""

    ext = _TLD_EXTRACTOR(raw) if _TLD_EXTRACTOR else None
    domain = ext.domain if ext else hostname.split(".")[0] if hostname else ""
    suffix = ext.suffix if ext else ""
    subdomain = ext.subdomain if ext else ""

    num_subdomains = len([s for s in subdomain.split(".") if s]) if subdomain else 0
    keyword_hits = sum(1 for kw in SUSPICIOUS_KEYWORDS if kw in raw.lower())

    registered_domain = f"{domain}.{suffix}" if suffix else domain
    brand_distance = min(
        (_levenshtein(domain, brand) for brand in POPULAR_BRAND_DOMAINS),
        default=99,
    )
    # Exact match to a known brand's real domain isn't typosquatting.
    if domain in POPULAR_BRAND_DOMAINS:
        brand_distance = 99

    special_chars = re.findall(r"[~!$^*()+={}\[\]|\\;:'\"<>,]", raw)

    host_info = _lookup_host_info(hostname) if (use_network and hostname) else HostLookupResult()

    features = {
        "url_length": len(raw),
        "hostname_length": len(hostname),
        "path_length": len(path),
        "query_length": len(query),
        "num_dots": raw.count("."),
        "num_hyphens": raw.count("-"),
        "num_underscores": raw.count("_"),
        "num_at": raw.count("@"),
        "num_percent": raw.count("%"),
        "num_digits": sum(c.isdigit() for c in raw),
        "num_params": query.count("=") if query else 0,
        "num_fragments": 1 if parts.fragment else 0,
        "digit_ratio": (sum(c.isdigit() for c in raw) / len(raw)) if raw else 0.0,
        "has_ip_address": int(_is_ip_host(hostname)),
        "has_https": int(parts.scheme == "https"),
        "is_shortener": int(registered_domain in SHORTENER_DOMAINS),
        "num_subdomains": num_subdomains,
        "suspicious_keyword_count": keyword_hits,
        "domain_entropy": _shannon_entropy(domain),
        "url_entropy": _shannon_entropy(raw),
        "tld_is_suspicious": int(suffix.split(".")[-1] in SUSPICIOUS_TLDS if suffix else False),
        "brand_edit_distance_min": brand_distance,
        "has_port": int(parts.port is not None),
        "double_extension": int(bool(re.search(r"\.\w{2,4}\.\w{2,4}$", path))),
        "count_special_chars": len(special_chars),
        "hostname_is_numeric_only": int(hostname.replace(".", "").isdigit() if hostname else False),
        "num_slashes_in_path": path.count("/"),
        "has_hex_encoding": len(re.findall(r"%[0-9a-fA-F]{2}", raw)),
        "tld_length": len(suffix),
        "contains_www": int(hostname.startswith("www.")),
        "char_repetition_max": _max_char_repetition(raw),
        "has_double_slash_redirect": int("//" in path),
        "domain_age_days": host_info.domain_age_days,
        "has_mx_record": host_info.has_mx_record,
    }
    return features
