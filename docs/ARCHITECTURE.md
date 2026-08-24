# TriShield Architecture

## System overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                              │
│              React + TypeScript dashboard (frontend/)             │
└───────────────────────────────┬───────────────────────────────────┘
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                     API LAYER (FastAPI, backend/)                 │
│   /predict/url  /predict/email  /predict/webpage  /feedback       │
│   /history  /analytics/summary  /auth/register  /auth/login       │
│   JWT auth (optional per-request) · rate limiting · validation    │
└───────────────┬─────────────────────────────────────┬─────────────┘
                 ▼                                     ▼
┌────────────────────────────┐        ┌─────────────────────────────┐
│  FEATURE EXTRACTION LAYER   │        │        PERSISTENCE           │
│  backend/app/ml/features/   │        │  SQLAlchemy models:          │
│  url_features / email_      │        │  User, Scan, ScanFeature,    │
│  features / web_features    │        │  Feedback, ModelVersion      │
└───────────────┬─────────────┘        └─────────────────────────────┘
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                 ML INFERENCE LAYER (backend/app/ml/)               │
│  url_model.joblib (XGBoost)  email_model.joblib (LightGBM+TF-IDF) │
│  web_model.joblib (XGBoost)                                       │
│  fusion.py  — weighted cross-channel score combination            │
│  explain.py — SHAP TreeExplainer → human-readable reasons         │
└──────────────────────────────────────────────────────────────────┘
```

`ml-training/` is the offline counterpart: it imports the exact same
`backend/app/ml/features/*` modules (via `sys.path` injection in
`ml-training/src/paths.py`) so there is a single source of truth for
feature engineering between training and serving — no risk of the
model being trained on a feature definition that drifts from what the
API computes at inference time.

## Why three independent models instead of one

The spec's three input types (URL, email, webpage) have almost no
overlapping structure — a URL is a short string, an email is
headers+text, a webpage is a DOM tree — so a single model would need
awkward shared representations for no benefit. Each channel gets its
own feature extractor and its own model, trained on the dataset that
actually matches that channel, then combined at request time (see
Fusion below). This also matches the "extensible... without retraining
from scratch" requirement: adding a new URL indicator means adding one
function to `url_features.py` and retraining only `url_model.joblib`.

## Datasets

| Channel | Dataset | Size | Source |
|---|---|---|---|
| URL | faizann24/Using-machine-learning-to-detect-malicious-URLs | 420,464 URLs (good/bad) | https://github.com/faizann24/Using-machine-learning-to-detect-malicious-URLs |
| URL (negative-class balance) | zer0h/top-1000000-domains | 100,000 domains (Tranco/Cisco-Umbrella-style ranking) | https://github.com/zer0h/top-1000000-domains |
| Email | Enron Spam Dataset (Metsis, Androutsopoulos & Paliouras, 2006) | 33,716 emails (spam/ham) | https://github.com/MWiechmann/enron_spam_data |
| Webpage | UCI "Phishing Websites" dataset (Mohammad, Thabtah & McCluskey, 2015) | 11,055 labelled instances, 30 features | https://github.com/vaibhavbichave/Phishing-URL-Detection |

Reproduce locally with `ml-training/data/fetch_datasets.sh`, then run
`prepare_url_dataset.py`, `prepare_email_dataset.py`,
`prepare_web_dataset.py` followed by `train_url.py`, `train_email.py`,
`train_web.py` (all in `ml-training/src/`).

### A dataset bias we found and fixed

An early version of the URL model, trained on the malicious-URL corpus
alone, flagged `https://www.wikipedia.org` and `https://github.com` as
phishing with >90% confidence. Root cause: in that corpus, "good" URLs
are almost always deep links (`pos-kupang.com/some/article`) while
"bad" URLs are disproportionately bare root domains — the model learned
"no path → phishing" as a shortcut. Fixing it required adding real
data, not tweaking a threshold: 20,000 known-legitimate bare root
domains (with varied `https://`/`www.` presence) were mixed into the
legitimate class (`prepare_url_dataset.py`), which corrected the bias
without hurting recall on real phishing URLs. This is exactly the kind
of false-positive risk the spec calls out as critical, and it only
surfaces when you test against real inputs shaped like what users
actually submit — synthetic or purely-lexical test cases would have
missed it.

### Class imbalance handling

- URL: 20k legitimate (corpus) + 20k top-domain-augmented legitimate +
  20k phishing/malicious → `scale_pos_weight` set on XGBoost to correct
  the resulting 2:1 imbalance.
- Email: Enron spam/ham is naturally balanced (~51/49); no rebalancing
  needed. `class_weight="balanced"` used regardless for robustness.
- Webpage: UCI dataset is mildly imbalanced (55.7%/44.3%);
  `class_weight="balanced"` on the Random Forest baseline, default
  XGBoost otherwise (tree boosting is fairly imbalance-tolerant at this
  ratio, confirmed by the FPR in `ml-training/reports/EVALUATION.md`).

## Web-content feature schema: what's live-computable and what isn't

The web-content model's feature *definitions* mirror the Mohammad et
al. UCI schema (`backend/app/ml/features/web_features.py`), but 5 of
the original 30 columns are dropped from **both** training and serving
so there is no train/serve skew:

- `WebsiteTraffic`, `PageRank`, `GoogleIndex`, `LinksPointingToPage` —
  need paid ranking/backlink APIs with no free equivalent reachable at
  inference time.
- `AbnormalURL` — compares the URL host to WHOIS registrant identity, a
  match that's too brittle to replicate reliably; `DNSRecording` (DNS
  resolution) is used as the practical legitimacy-signal substitute.

The remaining 25 features are computed live via `requests` +
BeautifulSoup (static HTML only — no JS execution). Three enrichments
(WHOIS domain age/registration length, DNS resolution, TLS certificate
validity) use raw sockets and can hang past their own timeout in
egress-restricted networks (WHOIS is port 43, not HTTP); these run
concurrently on a thread pool with a **hard** 0.8s wall-clock cap per
lookup (`_await_future` in `web_features.py`) so a stalled lookup can
never blow the <2s latency budget — it just falls back to a neutral
"unknown" value. Confirmed empirically: `predict_webpage()` stays under
~1.5s end-to-end even when all three raw-socket lookups are fully
blocked by network policy.

Extending to JS-rendered pages (Selenium/Playwright, mentioned as
optional in the spec) is a drop-in change: swap the `fetch_page()`
function in `web_features.py` for a browser-rendered fetch; every
downstream feature computation operates on the resulting HTML string
unchanged.

## Fusion: why rule-based, not a trained meta-learner

The spec offers two options for combining channel scores: a trained
stacking meta-learner, or a weighted rule-based combiner. A meta-learner
needs joint-labelled examples — the same real-world incident scored on
multiple channels with one ground-truth label — and no such dataset
exists here (the three training sources are disjoint: a URL corpus, an
email corpus, a webpage corpus). Fabricating "joint" labels by pairing
unrelated samples would teach the meta-learner a fake correlation.

Instead, fusion happens *within* a request wherever it naturally spans
channels (`backend/app/ml/fusion.py`):
- **`/predict/email`**: 70% weight on the email content model's score,
  30% distributed across the URL model's score for every embedded link
  (up to 5) — a legitimate-looking email with one phishing link should
  still be flagged.
- **`/predict/webpage`**: 60% web-content model, 40% URL-structure
  model on the page's own address — lexical tricks in the URL matter
  alongside what the DOM looks like.
- **`/predict/url`**: URL model only (no other channel applies to a
  bare URL string).

`fuse_scores()` takes a generic list of `ChannelScore(channel, score,
weight)` so a trained meta-learner can be substituted later without
touching the callers, if real joint-incident data is ever collected
(e.g. via the `/feedback` loop, over enough volume).

## Explainability

`backend/app/ml/explain.py` runs SHAP's `TreeExplainer` against
whichever tree model produced the prediction (XGBoost/LightGBM/Random
Forest all supported), ranks features by SHAP contribution toward the
"phishing" class, and maps the top ones through a per-channel template
dictionary (e.g. `domain_age_days` below 30 → "domain was registered
only N day(s) ago") to produce plain-language reasons rather than raw
feature names. `TreeExplainer` instances are cached per model and
pre-warmed at API startup (`_warmup_models()` in `main.py`) so the
one-time construction cost (~300-600ms) never lands on a user's first
request — subsequent calls are ~10-15ms.

The email model is trained on a concatenation of TF-IDF token columns
and the 17 heuristic structural features; SHAP is run over the full
~3000-dim vector for accurate attribution, but only the structural
feature names have a reason template, so TF-IDF token contributions
are ranked but never surfaced as (uninterpretable) reasons.

## Known limitations

- **Static HTML only.** No JavaScript execution, so DOM manipulated by
  client-side JS after load isn't seen. Documented extension point
  above.
- **WHOIS/DNS/TLS enrichments degrade gracefully but add no signal in
  egress-restricted environments.** They're real, live checks in a
  normal deployment with direct internet egress.
- **Email/spam ≠ phishing exactly.** Enron Spam is the standard corpus
  cited for this task in the literature, and shares the lexical/
  structural signals this project targets, but a purely commercial-spam
  email and a credential-phishing email aren't identical distributions.
- **Fusion is rule-based, not learned**, for the data-availability
  reason above. Weights (0.7/0.3, 0.6/0.4) are reasoned defaults, not
  fit to held-out fused-accuracy data — there is no such data.
- **No browser extension, no live email-inbox integration** — out of
  scope per the original spec (section 3).
