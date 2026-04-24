import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlparse
from docx import Document
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Advanced IA Audit Tool", layout="wide")
st.title("Advanced IA Audit Tool (Public Website)")

# -------------------------------
# Safe Import for BeautifulSoup
# -------------------------------
BS4_AVAILABLE = True
try:
    from bs4 import BeautifulSoup
except ImportError:
    BS4_AVAILABLE = False

# -------------------------------
# Inputs
# -------------------------------
uploaded_file = st.file_uploader("Upload URL List (CSV/Excel)", type=["csv", "xlsx"])
sitemap_url = st.text_input("Optional: Enter Sitemap URL")

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
def fetch_sitemap_urls(sitemap_url):
    try:
        response = requests.get(sitemap_url, timeout=10)
        root = ET.fromstring(response.content)
        return set([elem.text for elem in root.iter() if "loc" in elem.tag])
    except:
        st.warning("Unable to fetch or parse sitemap.")
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
# HTTP + Title Fetch (Safe)
# -------------------------------
def fetch_page_data(url):
    try:
        response = requests.get(url, timeout=5, allow_redirects=True)

        status = response.status_code
        final_url = response.url
        title = ""

        # Only attempt parsing if bs4 is available
        if BS4_AVAILABLE:
            try:
                soup = BeautifulSoup(response.text, "lxml")
            except:
                soup = BeautifulSoup(response.text, "html.parser")

            if soup.title and soup.title.string:
                title = soup.title.string.strip()

        return status, final_url, title

    except requests.exceptions.RequestException:
        return None, None, None


def enrich_http_data(df):
    statuses, finals, titles = [], [], []

    progress = st.progress(0)
    total = len(df)

    for i, url in enumerate(df["URL"]):
        status, final_url, title = fetch_page_data(url)

        statuses.append(status)
        finals.append(final_url)
        titles.append(title)

        progress.progress((i + 1) / total)

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
    section_counts = df["section"].value_counts()

    # Orphan detection
    if sitemap_urls:
        orphan = sitemap_urls - set(df["URL"])
        orphan_pct = round((len(orphan) / len(sitemap_urls)) * 100, 2)
    else:
        orphan_pct = "N/A"

    # HTTP metrics
    broken = df[df["status"] >= 400].shape[0]
    redirect = df[df["status"].between(300, 399)].shape[0]

    # Duplicate titles
    duplicate_titles = df["title"].duplicated().sum() if BS4_AVAILABLE else "N/A"

    metrics = {
        "Total Pages": total,
        "Unique Pages": unique,
        "% Duplicate URLs": round((duplicates / total) * 100, 2) if total else 0,
        "Avg Depth": avg_depth,
        "Max Depth": df["depth"].max(),
        "% Orphan Pages": orphan_pct,
        "Broken Pages": broken,
        "Redirects": redirect,
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
    doc.add_paragraph("Automated IA audit based on publicly accessible website data.")

    doc.add_heading("Metrics", 1)
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

    st.info("Processing URLs... this may take time")

    df = enrich_http_data(df)

    sitemap_urls = fetch_sitemap_urls(sitemap_url) if sitemap_url else set()

    metrics, section_counts = compute_metrics(df, sitemap_urls)

    st.subheader("Metrics")
    st.json(metrics)

    st.subheader("Section Distribution")
    st.bar_chart(section_counts)

    st.subheader("Sample Data")
    st.dataframe(df.head())

    # CSV Download
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download Full Dataset", csv, "audit_output.csv")

    # Word Report
    doc = generate_report(metrics, section_counts)
    path = "/mnt/data/IA_Audit_Report.docx"
    doc.save(path)

    with open(path, "rb") as f:
        st.download_button("Download Word Report", f, "IA_Audit_Report.docx")