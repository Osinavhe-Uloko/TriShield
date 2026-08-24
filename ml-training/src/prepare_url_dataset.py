"""Build the processed URL feature dataset from the raw labelled URL corpus.

Sources:
  1. faizann24/Using-machine-learning-to-detect-malicious-URLs
     (420,464 URLs labelled good/bad — a widely used malicious-URL corpus
     combining phishing, spam and drive-by-download URLs; the shared
     "bad" label is treated as the phishing/malicious positive class).
  2. zer0h/top-1000000-domains (a Tranco/Cisco-Umbrella-style top
     popularity ranking, per the "Alexa/Tranco Top 1M" source the spec
     recommends for negative-class balance).

Why #2 is needed: nearly every "good" URL in corpus #1 is a deep link
(e.g. ``pos-kupang.com/some/article``) while every "bad" URL is far more
often a bare root domain. A model trained on #1 alone learns "no
path => phishing" as a shortcut and flags bare root URLs like
``https://www.wikipedia.org`` as phishing with high confidence — a
critical false positive. Injecting a large sample of known-legitimate
bare root domains (with and without scheme/``www.``, matching how real
users paste URLs) into the legitimate class corrects this bias. See
docs/ARCHITECTURE.md for detail and the before/after evaluation.
"""
import csv
import sys

import pandas as pd
from sklearn.model_selection import train_test_split

from paths import DATA_RAW, DATA_PROCESSED
from app.ml.features.url_features import extract_url_features, URL_FEATURE_NAMES

RAW_FILE = DATA_RAW / "malicious_urls_raw.csv"
TOP_DOMAINS_FILE = DATA_RAW / "top_domains.txt"
MAX_PER_CLASS = 20000
TOP_DOMAINS_SAMPLE = 20000


def load_top_domain_urls(n: int) -> list[str]:
    with open(TOP_DOMAINS_FILE, encoding="utf-8", errors="replace") as f:
        domains = [line.strip() for line in f if line.strip()][:n]
    urls = []
    for i, domain in enumerate(domains):
        # Vary scheme/www presence to match how real users paste URLs,
        # rather than only ever the bare "example.com" form.
        if i % 3 == 0:
            urls.append(f"https://{domain}")
        elif i % 3 == 1:
            urls.append(f"https://www.{domain}")
        else:
            urls.append(domain)
    return urls


def main():
    csv.field_size_limit(sys.maxsize)
    rows = {"good": [], "bad": []}
    with open(RAW_FILE, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 2:
                continue
            url, label = row[0], row[-1].strip().lower()
            if label in rows and len(rows[label]) < MAX_PER_CLASS:
                rows[label].append(url)
            if len(rows["good"]) >= MAX_PER_CLASS and len(rows["bad"]) >= MAX_PER_CLASS:
                break

    top_domain_urls = load_top_domain_urls(TOP_DOMAINS_SAMPLE)
    print(f"Sampled: good={len(rows['good'])} bad={len(rows['bad'])} +top_domains={len(top_domain_urls)}")

    records = []
    for label_name, is_phishing in (("bad", 1), ("good", 0)):
        for url in rows[label_name]:
            feats = extract_url_features(url, use_network=False)
            feats["label"] = is_phishing
            records.append(feats)
    for url in top_domain_urls:
        feats = extract_url_features(url, use_network=False)
        feats["label"] = 0
        records.append(feats)

    df = pd.DataFrame(records, columns=URL_FEATURE_NAMES + ["label"])
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)

    train_df, test_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df["label"]
    )
    train_df.to_csv(DATA_PROCESSED / "url_train.csv", index=False)
    test_df.to_csv(DATA_PROCESSED / "url_test.csv", index=False)
    print(f"Wrote {len(train_df)} train / {len(test_df)} test rows to data/processed/")


if __name__ == "__main__":
    main()
