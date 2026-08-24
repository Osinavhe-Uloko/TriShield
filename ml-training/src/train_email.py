"""Train the email channel: TF-IDF (subject+body) + heuristic structural
features, feeding a LightGBM classifier (per spec section 8's
"TF-IDF + LightGBM" option). A Logistic Regression on the same combined
feature space serves as the interpretable baseline."""
import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp
from lightgbm import LGBMClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from paths import DATA_PROCESSED, MODELS_DIR
from evaluate import evaluate_and_report, measure_latency_ms
from app.ml.features.email_features import EMAIL_FEATURE_NAMES, extract_email_features

MAX_TFIDF_FEATURES = 3000


def build_matrix(df, vectorizer, scaler=None, fit=False):
    text_matrix = vectorizer.fit_transform(df["text"]) if fit else vectorizer.transform(df["text"])
    struct = df[EMAIL_FEATURE_NAMES].to_numpy(dtype=float)
    struct = scaler.fit_transform(struct) if fit else scaler.transform(struct)
    return sp.hstack([text_matrix, sp.csr_matrix(struct)]).tocsr()


def main():
    train_df = pd.read_csv(DATA_PROCESSED / "email_train.csv").fillna({"text": ""})
    test_df = pd.read_csv(DATA_PROCESSED / "email_test.csv").fillna({"text": ""})

    vectorizer = TfidfVectorizer(max_features=MAX_TFIDF_FEATURES, stop_words="english", ngram_range=(1, 2))
    scaler = StandardScaler()

    X_train = build_matrix(train_df, vectorizer, scaler, fit=True)
    X_test = build_matrix(test_df, vectorizer, scaler, fit=False)
    y_train, y_test = train_df["label"], test_df["label"]

    baseline = LogisticRegression(max_iter=1000, class_weight="balanced")
    baseline.fit(X_train, y_train)
    base_pred = baseline.predict(X_test)
    base_proba = baseline.predict_proba(X_test)[:, 1]
    evaluate_and_report("email_baseline_logreg", y_test, base_pred, base_proba)

    model = LGBMClassifier(
        n_estimators=400, max_depth=8, learning_rate=0.05,
        class_weight="balanced", random_state=42, n_jobs=-1, verbose=-1,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    evaluate_and_report("email_lightgbm", y_test, y_pred, y_proba)

    latency_ms = measure_latency_ms(
        extract_email_features, raw_email="From: a@b.com\nSubject: hi\n\nVerify your account now!"
    )
    print(f"  feature extraction latency: {latency_ms:.3f} ms/email")

    joblib.dump(model, MODELS_DIR / "email_model.joblib")
    joblib.dump(baseline, MODELS_DIR / "email_baseline_logreg.joblib")
    joblib.dump(vectorizer, MODELS_DIR / "email_tfidf_vectorizer.joblib")
    joblib.dump(scaler, MODELS_DIR / "email_scaler.joblib")
    print("Saved email_model.joblib + tfidf vectorizer + scaler")


if __name__ == "__main__":
    main()
