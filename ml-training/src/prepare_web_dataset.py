"""Build the processed webpage/DOM feature dataset from the UCI
"Phishing Websites" dataset (Mohammad, Thabtah & McCluskey, 2015;
11,055 labelled instances, 30 structural/URL/host features).

Column mapping to our live-computable ``WEB_FEATURE_NAMES`` schema
(see backend/app/ml/features/web_features.py for the full rationale):
  - 25 of the original 30 columns map 1:1 to features we can compute
    live from a fetched page with no paid APIs.
  - 5 columns are dropped from BOTH training and serving so there is no
    train/serve skew: WebsiteTraffic, PageRank, GoogleIndex and
    LinksPointingToPage need paid ranking/backlink APIs with no free
    equivalent; AbnormalURL needs a WHOIS-registrant-identity match
    that is too brittle to replicate reliably.
  - DNSRecording is used as the ``dns_resolves`` proxy in place of
    AbnormalURL (both are DNS/WHOIS legitimacy signals in the original
    paper; DNS resolution is the one we can cheaply verify live).

Original label convention: class == 1 legitimate, class == -1 phishing.
"""
import pandas as pd
from sklearn.model_selection import train_test_split

from paths import DATA_RAW, DATA_PROCESSED
from app.ml.features.web_features import WEB_FEATURE_NAMES

RAW_FILE = DATA_RAW / "uci_phishing_websites.csv"

COLUMN_MAP = {
    "UsingIP": "using_ip",
    "LongURL": "long_url",
    "ShortURL": "short_url",
    "Symbol@": "has_at_symbol",
    "Redirecting//": "double_slash_redirect",
    "PrefixSuffix-": "prefix_suffix",
    "SubDomains": "sub_domains",
    "HTTPS": "https_valid",
    "DomainRegLen": "domain_reg_len",
    "Favicon": "favicon_external",
    "NonStdPort": "non_std_port",
    "HTTPSDomainURL": "https_in_domain",
    "RequestURL": "request_url_external_pct",
    "AnchorURL": "anchor_url_external_pct",
    "LinksInScriptTags": "links_in_tags_external_pct",
    "ServerFormHandler": "server_form_handler",
    "InfoEmail": "info_email",
    "DNSRecording": "dns_resolves",
    "WebsiteForwarding": "website_forwarding_count",
    "StatusBarCust": "status_bar_custom",
    "DisableRightClick": "disable_right_click",
    "UsingPopupWindow": "using_popup_window",
    "IframeRedirection": "iframe_present",
    "AgeofDomain": "domain_age_ok",
    "StatsReport": "blacklist_pattern_match",
}


def main():
    df = pd.read_csv(RAW_FILE)
    out = df.rename(columns=COLUMN_MAP)[list(COLUMN_MAP.values())].copy()
    out["label"] = (df["class"] == -1).astype(int)
    out = out[WEB_FEATURE_NAMES + ["label"]]
    out = out.sample(frac=1.0, random_state=42).reset_index(drop=True)

    train_df, test_df = train_test_split(
        out, test_size=0.2, random_state=42, stratify=out["label"]
    )
    train_df.to_csv(DATA_PROCESSED / "web_train.csv", index=False)
    test_df.to_csv(DATA_PROCESSED / "web_test.csv", index=False)
    print(f"Wrote {len(train_df)} train / {len(test_df)} test rows to data/processed/")


if __name__ == "__main__":
    main()
