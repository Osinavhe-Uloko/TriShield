from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import Base, engine
from app.api.routes import auth, url, email, webpage, feedback, history, analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _warmup_models()
    yield


def _warmup_models():
    """Pre-builds SHAP explainers at startup so the first real request
    isn't penalized by one-time explainer construction cost."""
    try:
        from app.ml.inference import predict_url, predict_email, predict_webpage

        predict_url("http://example.com")
        predict_email(raw_email="From: a@b.com\nSubject: hi\n\nhello")
        predict_webpage("http://example.com", use_network=False)
    except Exception:
        pass


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Intelligent phishing detection across URL, email and webpage "
        "channels, with fused risk scoring and explainable verdicts."
    ),
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(url.router)
app.include_router(email.router)
app.include_router(webpage.router)
app.include_router(feedback.router)
app.include_router(history.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"status": "ok"}
