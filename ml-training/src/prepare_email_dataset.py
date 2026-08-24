"""Build the processed email dataset (heuristic features) from the Enron
Spam corpus (Metsis, Androutsopoulos & Paliouras 2006; CSV mirror by
MWiechmann, 33,716 labelled emails: Enron ham + assembled spam).

Spam and phishing are not identical, but share the lexical/structural
signals this system targets (urgency language, suspicious links, sender
spoofing) and Enron+SpamAssassin are exactly the corpora the project
brief cites for the email channel. The raw subject+body text is also
kept in the processed CSV so training scripts can build a TF-IDF
vectorizer on top of the same rows.
"""
import pandas as pd
from sklearn.model_selection import train_test_split

from paths import DATA_RAW, DATA_PROCESSED
from app.ml.features.email_features import extract_email_features, EMAIL_FEATURE_NAMES

RAW_FILE = DATA_RAW / "enron_spam_data.csv"
MAX_PER_CLASS = 16000


def main():
    df = pd.read_csv(RAW_FILE, usecols=["Subject", "Message", "Spam/Ham"]).dropna(subset=["Message"])
    df["Subject"] = df["Subject"].fillna("")

    records = []
    for label_name, group in df.groupby("Spam/Ham"):
        is_phishing = 1 if label_name == "spam" else 0
        group = group.sample(n=min(MAX_PER_CLASS, len(group)), random_state=42)
        for _, row in group.iterrows():
            headers = {"Subject": row["Subject"]}
            feats = extract_email_features(headers=headers, body=str(row["Message"]))
            feats["text"] = f"{row['Subject']}\n{row['Message']}"
            feats["label"] = is_phishing
            records.append(feats)

    out_df = pd.DataFrame(records, columns=EMAIL_FEATURE_NAMES + ["text", "label"])
    out_df = out_df.sample(frac=1.0, random_state=42).reset_index(drop=True)

    train_df, test_df = train_test_split(
        out_df, test_size=0.2, random_state=42, stratify=out_df["label"]
    )
    train_df.to_csv(DATA_PROCESSED / "email_train.csv", index=False)
    test_df.to_csv(DATA_PROCESSED / "email_test.csv", index=False)
    print(f"Wrote {len(train_df)} train / {len(test_df)} test rows to data/processed/")


if __name__ == "__main__":
    main()
