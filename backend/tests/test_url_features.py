from app.ml.features.url_features import extract_url_features, URL_FEATURE_NAMES
from app.ml.inference import predict_url


def test_feature_vector_has_all_expected_keys():
    feats = extract_url_features("https://example.com/path?x=1")
    assert set(feats.keys()) == set(URL_FEATURE_NAMES)


def test_ip_address_host_detected():
    feats = extract_url_features("http://192.168.1.1/login")
    assert feats["has_ip_address"] == 1


def test_https_detected():
    assert extract_url_features("https://example.com")["has_https"] == 1
    assert extract_url_features("http://example.com")["has_https"] == 0


def test_shortener_detected():
    assert extract_url_features("http://bit.ly/abc123")["is_shortener"] == 1
    assert extract_url_features("http://example.com/abc123")["is_shortener"] == 0


def test_suspicious_keywords_counted():
    feats = extract_url_features("http://example.com/login/verify/secure")
    assert feats["suspicious_keyword_count"] >= 3


def test_typosquat_brand_distance_low_for_lookalike():
    feats = extract_url_features("http://paypa1.com")
    assert feats["brand_edit_distance_min"] <= 2


def test_legitimate_bare_domain_not_flagged_phishing():
    for url in ("https://www.wikipedia.org", "https://google.com", "https://github.com"):
        result = predict_url(url)
        assert result["verdict"] == "legitimate", f"{url} incorrectly flagged: {result['risk_score']}"


def test_obvious_phishing_url_flagged():
    result = predict_url("http://secure-paypal-verify-account.tk/login")
    assert result["verdict"] == "phishing"
    assert result["risk_score"] > 0.5
    assert len(result["reasons"]) > 0
