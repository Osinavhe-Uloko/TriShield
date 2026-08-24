import sys
from pathlib import Path

ML_TRAINING_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ML_TRAINING_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
DATA_RAW = ML_TRAINING_DIR / "data" / "raw"
DATA_PROCESSED = ML_TRAINING_DIR / "data" / "processed"
MODELS_DIR = ML_TRAINING_DIR / "models"
REPORTS_DIR = ML_TRAINING_DIR / "reports"

# Reuse the exact feature-extraction code the FastAPI backend serves with,
# so there is a single source of truth between training and inference.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for d in (DATA_PROCESSED, MODELS_DIR, REPORTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
