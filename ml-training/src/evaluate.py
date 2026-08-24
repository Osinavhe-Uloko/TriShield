"""Shared evaluation helper: computes and persists the metrics the spec
requires (section 9) for a trained binary classifier."""
import json
import time

import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix,
)

from paths import REPORTS_DIR


def evaluate_and_report(name: str, y_true, y_pred, y_proba, extra: dict | None = None) -> dict:
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) else 0.0

    metrics = {
        "channel": name,
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1_score": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, y_proba),
        "pr_auc": average_precision_score(y_true, y_proba),
        "false_positive_rate": fpr,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "n_test_samples": int(len(y_true)),
    }
    if extra:
        metrics.update(extra)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_DIR / f"{name}_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n=== {name} evaluation ===")
    for k in ("accuracy", "precision", "recall", "f1_score", "roc_auc", "pr_auc", "false_positive_rate"):
        print(f"  {k:22s}: {metrics[k]:.4f}")
    print(f"  confusion_matrix      : {metrics['confusion_matrix']}")
    return metrics


def measure_latency_ms(fn, *args, n=50, **kwargs) -> float:
    start = time.perf_counter()
    for _ in range(n):
        fn(*args, **kwargs)
    return ((time.perf_counter() - start) / n) * 1000
