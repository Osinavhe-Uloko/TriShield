# TriShield — Intelligent Phishing Detection System

A full-stack, machine-learning-powered phishing detection system that
analyzes three independent signal sources — **URLs**, **email content
+ headers**, and **rendered webpage/DOM content** — and returns an
explainable verdict (not just phishing/legitimate, but *why*).

- Trained on real, cited public datasets (~450k labelled examples across
  the three channels — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).
- 94-98% accuracy per channel, ROC-AUC 0.98-0.998 — full metrics in
  [ml-training/reports/EVALUATION.md](ml-training/reports/EVALUATION.md).
- Every verdict comes with SHAP-derived, human-readable reasons
  ("domain registered 3 days ago", "connection is not encrypted") —
  not a black-box score.
- <2s inference latency end-to-end, including live webpage fetching.

## Quick start

### Option A: Docker Compose (recommended)

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API + docs: http://localhost:8000/docs

### Option B: Run locally

**Backend** (Python 3.11+):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Trained model artifacts already ship in `backend/app/ml/artifacts/` —
no training step required to run the API. Defaults to SQLite
(`backend/trishield.db`); set `DATABASE_URL` to point at Postgres for
production (see `docker-compose.yml`).

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173. The dev server proxies `/api` to
`http://localhost:8000` (see `frontend/vite.config.ts`).

### Retraining the models

```bash
cd ml-training
pip install -r requirements.txt
./data/fetch_datasets.sh          # downloads the 3 raw datasets (~90MB)
cd src
python3 prepare_url_dataset.py && python3 train_url.py
python3 prepare_email_dataset.py && python3 train_email.py
python3 prepare_web_dataset.py && python3 train_web.py
python3 generate_report.py        # writes reports/EVALUATION.md + roc_curves.png
```

Copy the resulting `ml-training/models/{url,email,web}_model.joblib`
(+ the email vectorizer/scaler) into `backend/app/ml/artifacts/` to
deploy a retrained model.

## Running tests

```bash
cd backend
pytest -q   # 28 tests: feature extraction + full API integration
```

## Project structure

```
TriShield/
├── backend/                  FastAPI service
│   ├── app/
│   │   ├── api/routes/       url, email, webpage, feedback, history, analytics, auth
│   │   ├── core/             config, JWT security, rate limiting
│   │   ├── db/               SQLAlchemy models + session
│   │   ├── ml/
│   │   │   ├── features/     url_features.py, email_features.py, web_features.py
│   │   │   ├── artifacts/    trained .joblib models (shipped, ready to serve)
│   │   │   ├── inference.py  loads models, runs per-channel prediction
│   │   │   ├── fusion.py     cross-channel score combination
│   │   │   └── explain.py    SHAP → human-readable reasons
│   │   └── schemas/          Pydantic request/response models
│   └── tests/                pytest suite (feature extraction + API)
├── ml-training/               offline training pipeline
│   ├── data/{raw,processed}   raw datasets (fetched, gitignored) + feature CSVs
│   ├── models/                training output (copied into backend/ to deploy)
│   ├── reports/               metrics JSON + EVALUATION.md + ROC curves
│   └── src/                   prepare_*.py, train_*.py, evaluate.py, generate_report.py
├── frontend/                  React + TypeScript + Tailwind dashboard
│   └── src/{pages,components,api}
├── docs/ARCHITECTURE.md       design rationale, dataset citations, limitations
└── docker-compose.yml
```

## API

Full interactive docs at `/docs` (Swagger) once the backend is
running. Summary:

| Endpoint | Description |
|---|---|
| `POST /api/v1/predict/url` | `{url}` → verdict, risk score, reasons, feature breakdown |
| `POST /api/v1/predict/email` | `{raw_email}` or `{headers, body}` → verdict fusing email content + embedded-link scores |
| `POST /api/v1/predict/webpage` | `{url}` → verdict fusing live-fetched DOM analysis + URL structure |
| `POST /api/v1/feedback` | `{scan_id, user_verdict}` → records user correction for future retraining |
| `GET /api/v1/history` | recent scans (optionally filtered by `user_id`) |
| `GET /api/v1/analytics/summary` | totals, verdict split, per-channel counts, feedback accuracy |
| `POST /api/v1/auth/register` / `/login` | JWT auth (optional — scans work anonymously too) |

All predict endpoints are rate-limited per IP and validate input before
feature extraction (malformed URLs are rejected with `422` before any
model runs).

## Tech stack

FastAPI · SQLAlchemy · scikit-learn · XGBoost · LightGBM · SHAP ·
BeautifulSoup4 · React 19 · TypeScript · Tailwind CSS 4 · Recharts ·
PostgreSQL (prod) / SQLite (dev) · Docker Compose.

## Scope

**In scope:** URL/email/webpage classification, cross-channel fusion,
explainability, REST API, web dashboard, reproducible training
pipeline on real cited datasets.

**Out of scope** (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for
why): real-time network traffic interception/blocking (this is a
detection/advisory tool, not a firewall), zero-day malware binary
analysis, a browser extension, full email-server/inbox integration,
and JavaScript-rendered DOM analysis (static HTML only — the code has a
documented extension point to add Selenium/Playwright rendering).

## Security & ethical notes

- Webpages are fetched via a standard HTTP client with a short
  timeout, no cookies/session persistence, and no execution of
  downloaded content — only HTML is parsed, never run.
- WHOIS/DNS/TLS enrichment lookups are capped at a hard 0.8s timeout
  each and fail safe to a neutral "unknown" value; they can never block
  a request indefinitely.
- API endpoints are rate-limited to discourage using this service as a
  phishing-testing oracle against arbitrary targets.
- No verdict is presented as certain — every response includes a
  confidence score, and the UI frames results as "risk" rather than an
  absolute pronouncement.
- Scan inputs are stored (for history/analytics/retraining) but
  truncated to 5,000 characters; there is no separate PII-scrubbing
  pass on email bodies — do not feed this system real user emails
  containing sensitive PII in a deployment without adding one.
