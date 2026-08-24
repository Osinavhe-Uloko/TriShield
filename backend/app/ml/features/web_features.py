"""Live webpage/DOM feature extraction.

Feature *definitions* here intentionally mirror the widely-cited
Mohammad/Thabtah/McCluskey "Phishing Websites" feature set (UCI ML
Repository), because that is the labelled dataset the web-content model
is trained on (see ml-training/src/prepare_web_dataset.py). Four of the
original 30 columns (WebsiteTraffic, PageRank, GoogleIndex,
LinksPointingToPage) require paid third-party ranking APIs with no free
equivalent reachable at inference time, and a fifth (AbnormalURL, which
compares the URL host to WHOIS registrant identity) is too brittle to
replicate reliably — all five are dropped from both training and
serving so there is no train/serve skew. See docs/ARCHITECTURE.md.

Rendering: pages are fetched with ``requests`` + parsed with
BeautifulSoup (static HTML only, no JS execution). The spec allows an
optional Selenium/Playwright-rendered DOM for JS-heavy pages; that is a
documented extension point (``render_with_browser`` hook below), not
implemented here to keep the service dependency-light and fast.
"""
from __future__ import annotations

import re
import ssl
import socket
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from urllib.parse import urlsplit, urljoin

import requests
from bs4 import BeautifulSoup

from app.ml.features.url_features import _is_ip_host, SHORTENER_DOMAINS, _TLD_EXTRACTOR

WEB_FEATURE_NAMES = [
    "using_ip", "long_url", "short_url", "has_at_symbol", "double_slash_redirect",
    "prefix_suffix", "sub_domains", "https_valid", "domain_reg_len", "favicon_external",
    "non_std_port", "https_in_domain", "request_url_external_pct", "anchor_url_external_pct",
    "links_in_tags_external_pct", "server_form_handler", "info_email", "dns_resolves",
    "website_forwarding_count", "status_bar_custom", "disable_right_click",
    "using_popup_window", "iframe_present", "domain_age_ok", "blacklist_pattern_match",
]

BLACKLIST_HOST_PATTERNS = [
    r"\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}",  # dashed IP masquerading as hostname
    r"secure.*-.*login", r"account.*update.*verify", r"[a-z0-9]{20,}\.(tk|ml|ga|cf)",
]

_REQUEST_TIMEOUT = 3
_HOST_LOOKUP_TIMEOUT = 0.8  # hard wall-clock cap per WHOIS/DNS/TLS check
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TriShieldScanner/1.0)"}

# WHOIS (port 43) and raw DNS resolution can hang well past their own
# socket timeout on some resolvers/firewalls (socket.setdefaulttimeout
# is not honoured by every code path). Running them on a thread pool
# with a hard future.result(timeout=...) guarantees the <2s API latency
# budget is respected even when these optional enrichments stall.
_HOST_LOOKUP_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="host-lookup")


def _with_timeout(fn, *args, default=None, timeout: float = _HOST_LOOKUP_TIMEOUT, **kwargs):
    future = _HOST_LOOKUP_POOL.submit(fn, *args, **kwargs)
    return _await_future(future, default=default, timeout=timeout)


def _await_future(future, default=None, timeout: float = _HOST_LOOKUP_TIMEOUT):
    if future is None:
        return default
    try:
        return future.result(timeout=timeout)
    except Exception:
        return default


def _registered_domain(hostname: str) -> str:
    if not hostname:
        return ""
    if _TLD_EXTRACTOR:
        ext = _TLD_EXTRACTOR(hostname)
        return f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
    return hostname


def _dns_resolves(hostname: str, timeout: float = 2.0) -> int:
    try:
        socket.setdefaulttimeout(timeout)
        socket.gethostbyname(hostname)
        return 1
    except Exception:
        return -1


def _https_cert_valid(hostname: str, timeout: float = 3.0) -> int:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                ssock.getpeercert()
        return 1
    except Exception:
        return 0


def _domain_age_info(hostname: str, timeout: float = 2.0):
    """Returns (domain_reg_len_ok, domain_age_ok) each in {-1,0,1}, 0=unknown."""
    try:
        import whois

        socket.setdefaulttimeout(timeout)
        w = whois.whois(hostname)
        created = w.creation_date
        expires = w.expiration_date
        created = created[0] if isinstance(created, list) else created
        expires = expires[0] if isinstance(expires, list) else expires
        import datetime

        reg_len_ok = 0
        age_ok = 0
        if created and expires:
            reg_len_days = (expires - created).days
            reg_len_ok = 1 if reg_len_days >= 365 else -1
        if created:
            age_days = (datetime.datetime.now() - created).days
            age_ok = 1 if age_days >= 180 else -1
        return reg_len_ok, age_ok
    except Exception:
        return 0, 0


def fetch_page(url: str):
    """Fetch a URL, following redirects. Returns (final_url, html, redirect_count) or (url, "", -1) on failure."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT, allow_redirects=True)
        return resp.url, resp.text, len(resp.history)
    except Exception:
        return url, "", -1


def extract_web_features(url: str, html: str | None = None, use_network: bool = True) -> dict:
    """Compute the webpage/DOM feature vector for ``url``.

    If ``html`` is not provided and ``use_network`` is True, the page is
    fetched live. If fetching fails or is disabled, structural features
    that require page content fall back to neutral/unknown values so the
    function never raises.
    """
    redirect_count = 0
    final_url = url
    if html is None and use_network:
        final_url, html, redirect_count = fetch_page(url)
    html = html or ""

    parts = urlsplit(final_url if "://" in final_url else "http://" + final_url)
    hostname = (parts.hostname or "").lower()
    registered_domain = _registered_domain(hostname)

    # Kick off the optional WHOIS/DNS/TLS enrichments in the background
    # now, in parallel, so their (capped) wait overlaps with the DOM
    # parsing below instead of adding to it sequentially.
    dns_future = https_future = age_future = None
    if use_network and hostname:
        dns_future = _HOST_LOOKUP_POOL.submit(_dns_resolves, hostname)
        age_future = _HOST_LOOKUP_POOL.submit(_domain_age_info, hostname)
        if parts.scheme == "https":
            https_future = _HOST_LOOKUP_POOL.submit(_https_cert_valid, hostname)

    soup = BeautifulSoup(html, "html.parser") if html else BeautifulSoup("", "html.parser")

    url_len = len(final_url)
    long_url = 1 if url_len < 54 else (0 if url_len <= 75 else -1)

    dot_count = hostname.count(".")
    sub_domains = 1 if dot_count <= 1 else (0 if dot_count == 2 else -1)

    def _external_ratio(tags: list, attr: str) -> float:
        total = 0
        external = 0
        for tag in tags:
            src = tag.get(attr)
            if not src:
                continue
            total += 1
            full = urljoin(final_url, src)
            src_host = urlsplit(full).hostname or ""
            if src_host and _registered_domain(src_host) != registered_domain:
                external += 1
        return (external / total) if total else 0.0

    req_ratio = _external_ratio(soup.find_all(["img", "script", "audio", "embed", "iframe"]), "src")
    request_url_pct = 1 if req_ratio < 0.22 else (0 if req_ratio <= 0.61 else -1)

    anchors = soup.find_all("a")
    anchor_external = 0
    anchor_total = 0
    for a in anchors:
        href = a.get("href") or ""
        anchor_total += 1
        if href.strip() in ("", "#") or href.lower().startswith(("javascript:void", "#")):
            anchor_external += 1
            continue
        full = urljoin(final_url, href)
        a_host = urlsplit(full).hostname or ""
        if a_host and _registered_domain(a_host) != registered_domain:
            anchor_external += 1
    anchor_ratio = (anchor_external / anchor_total) if anchor_total else 0.0
    anchor_url_pct = 1 if anchor_ratio < 0.31 else (0 if anchor_ratio <= 0.67 else -1)

    links_ratio = _external_ratio(soup.find_all("link"), "href")
    links_in_tags_pct = 1 if links_ratio < 0.17 else (0 if links_ratio <= 0.81 else -1)

    forms = soup.find_all("form")
    server_form_handler = 1
    for form in forms:
        action = (form.get("action") or "").strip()
        if action in ("", "about:blank"):
            server_form_handler = -1
            break
        full = urljoin(final_url, action)
        if _registered_domain(urlsplit(full).hostname or "") != registered_domain:
            server_form_handler = 0

    favicon = soup.find("link", rel=lambda v: v and "icon" in v.lower())
    favicon_external = 1
    if favicon and favicon.get("href"):
        fav_host = urlsplit(urljoin(final_url, favicon["href"])).hostname or ""
        if fav_host and _registered_domain(fav_host) != registered_domain:
            favicon_external = -1

    reg_len_ok, age_ok = _await_future(age_future, default=(0, 0))
    https_valid = _await_future(https_future, default=0) if parts.scheme == "https" else -1
    dns_resolves = _await_future(dns_future, default=0)

    features = {
        "using_ip": 1 if not _is_ip_host(hostname) else -1,
        "long_url": long_url,
        "short_url": -1 if registered_domain in SHORTENER_DOMAINS else 1,
        "has_at_symbol": -1 if "@" in final_url else 1,
        "double_slash_redirect": -1 if "//" in parts.path else 1,
        "prefix_suffix": -1 if "-" in hostname.split(":")[0] else 1,
        "sub_domains": sub_domains,
        "https_valid": https_valid,
        "domain_reg_len": reg_len_ok,
        "favicon_external": favicon_external,
        "non_std_port": -1 if parts.port and parts.port not in (80, 443) else 1,
        "https_in_domain": -1 if "https" in hostname.replace("www.", "") else 1,
        "request_url_external_pct": request_url_pct,
        "anchor_url_external_pct": anchor_url_pct,
        "links_in_tags_external_pct": links_in_tags_pct,
        "server_form_handler": server_form_handler,
        "info_email": -1 if re.search(r"mailto:|\.submit\(", html, re.IGNORECASE) else 1,
        "dns_resolves": dns_resolves,
        "website_forwarding_count": (
            1 if redirect_count <= 1 else (0 if redirect_count <= 3 else -1)
        ) if redirect_count >= 0 else 0,
        "status_bar_custom": -1 if re.search(r"onmouseover\s*=.*window\.status", html, re.IGNORECASE) else 1,
        "disable_right_click": -1 if re.search(r"event\.button\s*==\s*2|contextmenu", html, re.IGNORECASE) else 1,
        "using_popup_window": -1 if re.search(r"window\.open\s*\(|prompt\s*\(", html, re.IGNORECASE) else 1,
        "iframe_present": -1 if soup.find_all("iframe") else 1,
        "domain_age_ok": age_ok,
        "blacklist_pattern_match": -1 if any(
            re.search(p, hostname, re.IGNORECASE) for p in BLACKLIST_HOST_PATTERNS
        ) else 1,
    }
    return features
