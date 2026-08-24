"""Train the webpage/DOM channel: Random Forest baseline + XGBoost
primary model on the live-computable feature subset (spec section 8's
"feature-based Random Forest" option for web content)."""
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV
from xgboost import XGBClassifier

from paths import DATA_PROCESSED, MODELS_DIR
from evaluate import evaluate_and_report
from app.ml.features.web_features import WEB_FEATURE_NAMES


def main():
    train_df = pd.read_csv(DATA_PROCESSED / "web_train.csv")
    test_df = pd.read_csv(DATA_PROCESSED / "web_test.csv")

    X_train, y_train = train_df[WEB_FEATURE_NAMES], train_df["label"]
    X_test, y_test = test_df[WEB_FEATURE_NAMES], test_df["label"]

    baseline = RandomForestClassifier(n_estimators=200, max_depth=10, class_weight="balanced", random_state=42, n_jobs=-1)
    baseline.fit(X_train, y_train)
    base_pred = baseline.predict(X_test)
    base_proba = baseline.predict_proba(X_test)[:, 1]
    evaluate_and_report("web_baseline_rf", y_test, base_pred, base_proba)

    param_grid = {"n_estimators": [200, 400], "max_depth": [5, 8], "learning_rate": [0.1, 0.2]}
    search = GridSearchCV(
        XGBClassifier(eval_metric="logloss", random_state=42, n_jobs=-1),
        param_grid, scoring="f1", cv=5, n_jobs=-1,
    )
    search.fit(X_train, y_train)
    model = search.best_estimator_
    print("Best params:", search.best_params_)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    evaluate_and_report("web_xgboost", y_test, y_pred, y_proba, extra={"best_params": search.best_params_})

    joblib.dump(model, MODELS_DIR / "web_model.joblib")
    joblib.dump(baseline, MODELS_DIR / "web_baseline_rf.joblib")
    print("Saved web_model.joblib")


if __name__ == "__main__":
    main()
