#!/usr/bin/env bash
# Downloads the three raw datasets used to train TriShield's models into
# ml-training/data/raw/. See docs/ARCHITECTURE.md and README.md for full
# citations, licensing notes and why each was chosen.
set -euo pipefail
cd "$(dirname "$0")/raw"

echo "Fetching malicious/phishing URL corpus (faizann24)..."
curl -fSL -o malicious_urls_raw.csv \
  "https://raw.githubusercontent.com/faizann24/Using-machine-learning-to-detect-malicious-URLs/master/data/data.csv"

echo "Fetching UCI Phishing Websites dataset (Mohammad, Thabtah & McCluskey, 2015)..."
curl -fSL -o uci_phishing_websites.csv \
  "https://raw.githubusercontent.com/vaibhavbichave/Phishing-URL-Detection/master/phishing.csv"

echo "Fetching Enron Spam dataset (Metsis, Androutsopoulos & Paliouras, 2006)..."
curl -fSL -o enron_spam_data.csv \
  "https://raw.githubusercontent.com/MWiechmann/enron_spam_data/master/enron_spam_data.zip"
python3 -c "import zipfile; zipfile.ZipFile('enron_spam_data.zip').extractall('.')" 2>/dev/null || true
if [ -f enron_spam_data.zip ]; then
  mv enron_spam_data.zip enron_spam_data.csv.zip
  python3 -c "import zipfile; zipfile.ZipFile('enron_spam_data.csv.zip').extractall('.')"
  rm enron_spam_data.csv.zip
fi

echo "Fetching top-domains popularity list (zer0h/top-1000000-domains, Tranco/Cisco-Umbrella style)..."
curl -fSL -o top_domains.txt \
  "https://raw.githubusercontent.com/zer0h/top-1000000-domains/master/top-100000-domains"

echo "All datasets downloaded to ml-training/data/raw/"
