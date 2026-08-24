def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_predict_url_phishing(client):
    resp = client.post("/api/v1/predict/url", json={"url": "http://secure-paypal-verify.tk/login"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "phishing"
    assert 0 <= body["risk_score"] <= 1
    assert body["latency_ms"] > 0
    assert "scan_id" in body


def test_predict_url_rejects_malformed(client):
    resp = client.post("/api/v1/predict/url", json={"url": "not a url!!"})
    assert resp.status_code == 422


def test_predict_email(client):
    resp = client.post(
        "/api/v1/predict/email",
        json={"raw_email": "From: a@b.com\nSubject: Verify your account now!\n\nClick http://192.168.1.1/x"},
    )
    assert resp.status_code == 200
    assert resp.json()["verdict"] in ("phishing", "legitimate")


def test_predict_email_requires_content(client):
    resp = client.post("/api/v1/predict/email", json={})
    assert resp.status_code == 422


def test_feedback_and_history_and_analytics(client):
    scan_resp = client.post("/api/v1/predict/url", json={"url": "https://www.wikipedia.org"})
    scan_id = scan_resp.json()["scan_id"]

    fb_resp = client.post("/api/v1/feedback", json={"scan_id": scan_id, "user_verdict": "legitimate"})
    assert fb_resp.status_code == 201

    history_resp = client.get("/api/v1/history")
    assert history_resp.status_code == 200
    assert any(item["id"] == scan_id for item in history_resp.json())

    analytics_resp = client.get("/api/v1/analytics/summary")
    assert analytics_resp.status_code == 200
    summary = analytics_resp.json()
    assert summary["total_scans"] >= 1
    assert summary["feedback_accuracy"] == 1.0


def test_feedback_unknown_scan_404(client):
    resp = client.post("/api/v1/feedback", json={"scan_id": "does-not-exist", "user_verdict": "phishing"})
    assert resp.status_code == 404


def test_register_and_login(client):
    resp = client.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "supersecret1"})
    assert resp.status_code == 201
    assert "access_token" in resp.json()

    login_resp = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "supersecret1"})
    assert login_resp.status_code == 200

    bad_login = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "wrong"})
    assert bad_login.status_code == 401
