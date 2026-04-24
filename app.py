import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="IA Audit Tool", layout="wide")
st.title("IA Audit Tool (Fast + Parallel)")

# -------------------------------
# Safe Imports
# -------------------------------
BS4_AVAILABLE = True
DOCX_AVAILABLE = True

try:
    from bs4 import BeautifulSoup
except ImportError:
    BS4_AVAILABLE = False

try:
    from docx import Document
except ImportError:
    DOCX_AVAILABLE = False

# -------------------------------
# Inputs
# -------------------------------
uploaded_file = st.file_uploader("Upload URL list (CSV or Excel)", type=["csv", "xlsx"])
sitemap_url = st.text_input("Optional: Sitemap URL")

# -------------------------------
# Load File
# -------------------------------
def load_file(file):
    try:
        if file.name.endswith(".csv"):
            return pd.read_csv(file)
        else:
            return pd.read_excel(file, engine="openpyxl")
    except Exception as e:
        st.error(f"Error reading file: {e}")
        st.stop()

# -------------------------------
# Normalize URL Column
# -------------------------------
def normalize_url_column(df):
    df.columns = [str(c).strip().lower() for c in df.columns]

    for col in df.columns:
        if col in ["url", "link"]:
            return df[[col]].rename(columns={col: "URL"})

    return df.iloc[:, [0]].rename(columns={df.columns[0]: "URL"})

# -------------------------------
# Sitemap Parser
# -------------------------------
def fetch_sitemap_urls(url):
    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        return set([elem.text for elem in root.iter() if "loc" in elem.tag])
    except:
        st.warning("Unable to fetch sitemap")
        return set()

# -------------------------------
# URL Enrichment
# -------------------------------
def enrich_urls(df):
    df["URL"] = df["URL"].astype(str)

    df["path"] = df["URL"].apply(lambda x: urlparse(x).path)
    df["depth"] = df["path"].apply(lambda x: len([p for p in x.split("/") if p]))
    df["section"] = df["path"].apply(
        lambda x: x.split("/")[1] if len(x.split("/")) > 1 else "root"
    )

    return df

# -------------------------------
# HTTP Fetch (with headers)
# -------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; IA-Audit-Bot/1.0)"
}

def fetch_page_data(url):
    try:
        response = requests.get(url, timeout=5, headers=HEADERS, allow_redirects=True)

        status = response.status_code
        final_url = response.url
        title = ""

        if BS4_AVAILABLE:
            try:
                soup = BeautifulSoup(response.text, "lxml")
            except:
                soup = BeautifulSoup(response.text, "html.parser")

            if soup.title and soup.title.string:
                title = soup.title.string.strip()

        return status, final_url, title

    except:
        return None, None, None

# -------------------------------
# 🚀 Parallel Processing
# -------------------------------
def enrich_http_data(df):
    urls = df["URL"].tolist()

    statuses = [None] * len(urls)
    finals = [None] * len(urls)
    titles = [""] * len(urls)

    progress = st.progress(0)

    def worker(idx, url):
        return idx, fetch_page_data(url)

    MAX_WORKERS = min(20, len(urls))  # safe limit

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(worker, i, url) for i, url in enumerate(urls)]

        for i, future in enumerate(as_completed(futures)):
            idx, (status, final_url, title) = future.result()

            statuses[idx] = status
            finals[idx] = final_url
            titles[idx] = title

            progress.progress((i + 1) / len(urls))

    df["status"] = statuses
    df["final_url"] = finals
    df["title"] = titles

    return df

# -------------------------------
# Metrics
# -------------------------------
def compute_metrics(df, sitemap_urls):
    total = len(df)
    unique = df["URL"].nunique()
    duplicates = total - unique

    avg_depth = round(df["depth"].mean(), 2)
    max_depth = df["depth"].max()

    section_counts = df["section"].value_counts()

    # Orphan pages
    if sitemap_urls:
        orphan = sitemap_urls - set(df["URL"])
        orphan_pct = round((len(orphan) / len(sitemap_urls)) * 100, 2)
    else:
        orphan_pct = "N/A"

    # HTTP metrics
    broken = df[df["status"] >= 400].shape[0]
    redirects = df[df["status"].between(300, 399)].shape[0]

    duplicate_titles = df["title"].duplicated().sum() if BS4_AVAILABLE else "N/A"

    metrics = {
        "Total Pages": total,
        "Unique Pages": unique,
        "% Duplicate URLs": round((duplicates / total) * 100, 2) if total else 0,
        "Avg Depth": avg_depth,
        "Max Depth": max_depth,
        "% Orphan Pages": orphan_pct,
        "Broken Pages": broken,
        "Redirects": redirects,
        "Duplicate Titles": duplicate_titles,
        "Top Section": section_counts.idxmax()
    }

    return metrics, section_counts

# -------------------------------
# Word Report
# -------------------------------
def generate_report(metrics, section_counts):
    doc = Document()
    doc.add_heading("IA Audit Report", 0)

    doc.add_heading("Executive Summary", 1)
    doc.add_paragraph("Automated IA audit using publicly available data.")

    doc.add_heading("Core Metrics", 1)
    for k, v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading("Section Distribution", 1)
    for section, count in section_counts.items():
        doc.add_paragraph(f"{section}: {count}")

    return doc

# -------------------------------
# Main Flow
# -------------------------------
if uploaded_file:
    df = load_file(uploaded_file)
    df = normalize_url_column(df).dropna()

    df = enrich_urls(df)

    st.info("Processing URLs in parallel...")

    df = enrich_http_data(df)

    sitemap_urls = fetch_sitemap_urls(sitemap_url) if sitemap_url else set()

    metrics, section_counts = compute_metrics(df, sitemap_urls)

    st.subheader("Metrics")
    st.json(metrics)

    st.subheader("Section Distribution")
    st.bar_chart(section_counts)

    st.subheader("Sample Data")
    st.dataframe(df.head())

    # CSV download
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download Full Dataset", csv, "audit_output.csv")

    # Word Report
    if DOCX_AVAILABLE:
        doc = generate_report(metrics, section_counts)
        path = "/mnt/data/IA_Audit_Report.docx"
        doc.save(path)

        with open(path, "rb") as f:
            st.download_button("Download Word Report", f, "IA_Audit_Report.docx")
    else:
        st.warning("Word report not available (missing python-docx)")