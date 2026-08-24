"""Train the URL channel: Logistic Regression baseline + XGBoost primary
model, with a small grid search + 5-fold CV, per spec sections 8-9."""
import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from paths import DATA_PROCESSED, MODELS_DIR
from evaluate import evaluate_and_report, measure_latency_ms
from app.ml.features.url_features import URL_FEATURE_NAMES, extract_url_features


def main():
    train_df = pd.read_csv(DATA_PROCESSED / "url_train.csv")
    test_df = pd.read_csv(DATA_PROCESSED / "url_test.csv")

    X_train, y_train = train_df[URL_FEATURE_NAMES], train_df["label"]
    X_test, y_test = test_df[URL_FEATURE_NAMES], test_df["label"]

    # --- Baseline: Logistic Regression ---
    scaler = StandardScaler().fit(X_train)
    baseline = LogisticRegression(max_iter=1000, class_weight="balanced")
    baseline.fit(scaler.transform(X_train), y_train)
    base_pred = baseline.predict(scaler.transform(X_test))
    base_proba = baseline.predict_proba(scaler.transform(X_test))[:, 1]
    evaluate_and_report("url_baseline_logreg", y_test, base_pred, base_proba)

    # --- Primary: XGBoost with a small grid search ---
    param_grid = {
        "n_estimators": [150, 300],
        "max_depth": [4, 6],
        "learning_rate": [0.1, 0.2],
    }
    scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    base_model = XGBClassifier(
        eval_metric="logloss", random_state=42, n_jobs=-1, scale_pos_weight=scale_pos_weight,
    )
    search = GridSearchCV(base_model, param_grid, scoring="f1", cv=5, n_jobs=-1)
    search.fit(X_train, y_train)
    model = search.best_estimator_
    print("Best params:", search.best_params_)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    metrics = evaluate_and_report(
        "url_xgboost", y_test, y_pred, y_proba, extra={"best_params": search.best_params_}
    )

    latency_ms = measure_latency_ms(extract_url_features, "https://secure-paypal-verify.tk/login?redirect=account")
    print(f"  feature extraction latency: {latency_ms:.3f} ms/url")

    joblib.dump(model, MODELS_DIR / "url_model.joblib")
    joblib.dump(baseline, MODELS_DIR / "url_baseline_logreg.joblib")
    joblib.dump(scaler, MODELS_DIR / "url_scaler.joblib")
    print(f"Saved url_model.joblib (feature importances available for SHAP explainability)")


if __name__ == "__main__":
    main()
