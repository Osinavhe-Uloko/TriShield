from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
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
    docs_url=None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/docs", include_in_schema=False)
def swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
        swagger_favicon_url="/static/swagger-ui/favicon.png",
    )


@app.get("/redoc", include_in_schema=False)
def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="/static/swagger-ui/redoc.standalone.js",
        redoc_favicon_url="/static/swagger-ui/favicon.png",
    )

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
