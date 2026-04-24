import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

st.set_page_config(page_title="IA Audit Tool", layout="wide")
st.title("IA Audit Tool (Client Report Ready)")

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

HEADERS = {"User-Agent": "Mozilla/5.0"}

# -------------------------------
# Load + Normalize
# -------------------------------
def load_file(file):
    return pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)

def normalize(df):
    df.columns = [str(c).lower() for c in df.columns]
    for col in df.columns:
        if col in ["url", "link"]:
            return df[[col]].rename(columns={col: "URL"})
    return df.iloc[:, [0]].rename(columns={df.columns[0]: "URL"})

# -------------------------------
# Enrich URLs
# -------------------------------
def enrich(df):
    df["path"] = df["URL"].apply(lambda x: urlparse(x).path)
    df["depth"] = df["path"].apply(lambda x: len([p for p in x.split("/") if p]))
    df["section"] = df["path"].apply(
        lambda x: x.split("/")[1] if len(x.split("/")) > 1 else "root"
    )
    return df

# -------------------------------
# Fetch Data (Parallel)
# -------------------------------
def fetch(url):
    try:
        r = requests.get(url, timeout=5, headers=HEADERS)
        title = ""
        if BS4_AVAILABLE:
            soup = BeautifulSoup(r.text, "lxml")
            title = soup.title.string.strip() if soup.title else ""
        return r.status_code, r.url, title
    except:
        return None, None, ""

def crawl(df):
    urls = df["URL"].tolist()
    status, final, title = [None]*len(urls), [None]*len(urls), [""]*len(urls)

    progress = st.progress(0)
    with ThreadPoolExecutor(max_workers=20) as exe:
        futures = {exe.submit(fetch, u): i for i, u in enumerate(urls)}

        for i, f in enumerate(as_completed(futures)):
            idx = futures[f]
            s, fu, t = f.result()
            status[idx], final[idx], title[idx] = s, fu, t
            progress.progress((i+1)/len(urls))

    df["status"], df["final_url"], df["title"] = status, final, title
    return df

# -------------------------------
# Sitemap
# -------------------------------
def get_sitemap(url):
    try:
        r = requests.get(url)
        root = ET.fromstring(r.content)
        return set([e.text for e in root.iter() if "loc" in e.tag])
    except:
        return set()

# -------------------------------
# Metrics
# -------------------------------
def metrics(df, sitemap):
    total = len(df)
    dup = total - df["URL"].nunique()

    sections = df["section"].value_counts()

    return {
        "Total Pages": total,
        "% Duplicate": round((dup/total)*100,2) if total else 0,
        "Avg Depth": round(df["depth"].mean(),2),
        "Max Depth": df["depth"].max(),
        "Broken Pages": df[df["status"]>=400].shape[0],
        "Redirects": df[df["status"].between(300,399)].shape[0],
        "Duplicate Titles": df["title"].duplicated().sum(),
        "% Orphan Pages": (
            round(len(sitemap - set(df["URL"])) / len(sitemap) * 100,2)
            if sitemap else "N/A"
        )
    }, sections

# -------------------------------
# 📄 Word Report
# -------------------------------
def build_word(metrics, sections):
    doc = Document()
    doc.add_heading("IA Audit Report", 0)

    doc.add_heading("Executive Summary", 1)
    doc.add_paragraph("Automated IA audit using publicly accessible data.")

    doc.add_heading("Key Metrics", 1)
    for k,v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading("Section Distribution", 1)
    for s,c in sections.items():
        doc.add_paragraph(f"{s}: {c}")

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# -------------------------------
# 📊 Excel Report
# -------------------------------
def build_excel(df, metrics, sections):
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Raw Data", index=False)
        pd.DataFrame(metrics.items(), columns=["Metric","Value"]).to_excel(writer, sheet_name="Metrics", index=False)
        sections.to_frame("Count").to_excel(writer, sheet_name="Sections")

    buffer.seek(0)
    return buffer

# -------------------------------
# Main
# -------------------------------
if uploaded_file:
    df = normalize(load_file(uploaded_file)).dropna()
    df = enrich(df)

    st.info("Running fast crawl...")
    df = crawl(df)

    sitemap = get_sitemap(sitemap_url) if sitemap_url else set()
    m, sections = metrics(df, sitemap)

    st.subheader("Metrics")
    st.json(m)

    st.bar_chart(sections)

    # Excel
    excel_file = build_excel(df, m, sections)
    st.download_button("Download Excel Report", excel_file, "IA_Report.xlsx")

    # Word
    if DOCX_AVAILABLE:
        word_file = build_word(m, sections)
        st.download_button("Download Word Report", word_file, "IA_Report.docx")
    else:
        st.warning("Word report unavailable (install python-docx)")