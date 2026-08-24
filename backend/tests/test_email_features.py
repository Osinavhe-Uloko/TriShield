from app.ml.features.email_features import extract_email_features, EMAIL_FEATURE_NAMES
from app.ml.inference import predict_email


PHISHING_SAMPLE = """From: PayPal Security <no-reply@paypal-secure-verify.tk>
Reply-To: support@totally-different.ru
Subject: URGENT: Your account will be suspended!
Authentication-Results: spf=fail dkim=fail

Dear customer, click here to verify your account immediately: http://192.168.1.5/login
Act now or your account will be closed!!!
"""

LEGIT_SAMPLE = "From: mom@gmail.com\nSubject: dinner tonight?\n\nHey, want to grab dinner at 7pm? Let me know."


def test_feature_vector_has_all_expected_keys():
    feats = extract_email_features(raw_email=PHISHING_SAMPLE)
    assert set(feats.keys()) == set(EMAIL_FEATURE_NAMES)


def test_reply_to_mismatch_detected():
    feats = extract_email_features(raw_email=PHISHING_SAMPLE)
    assert feats["sender_replyto_mismatch"] == 1


def test_spf_dkim_failures_detected():
    feats = extract_email_features(raw_email=PHISHING_SAMPLE)
    assert feats["spf_fail"] == 1
    assert feats["dkim_fail"] == 1


def test_urgency_phrases_counted():
    feats = extract_email_features(raw_email=PHISHING_SAMPLE)
    assert feats["num_urgency_phrases"] >= 3


def test_phishing_email_flagged():
    result = predict_email(raw_email=PHISHING_SAMPLE)
    assert result["verdict"] == "phishing"
    assert result["risk_score"] > 0.5
    assert len(result["reasons"]) > 0


def test_legitimate_email_not_flagged():
    result = predict_email(raw_email=LEGIT_SAMPLE)
    assert result["verdict"] == "legitimate"
