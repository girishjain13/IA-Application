import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
from io import BytesIO

# -------------------------------
# Page Config + Styling
# -------------------------------
st.set_page_config(page_title="IA Audit Tool", layout="wide")

st.markdown("""
<style>
.metric-card {
    background-color: #1f2937;
    padding: 15px;
    border-radius: 10px;
    text-align: center;
    color: white;
}
</style>
""", unsafe_allow_html=True)

st.title("🚀 IA Audit Tool")

# -------------------------------
# Safe Imports
# -------------------------------
BS4_AVAILABLE = True
DOCX_AVAILABLE = True
EXCEL_AVAILABLE = True

try:
    from bs4 import BeautifulSoup
except:
    BS4_AVAILABLE = False

try:
    from docx import Document
except:
    DOCX_AVAILABLE = False

try:
    import openpyxl
except:
    EXCEL_AVAILABLE = False

HEADERS = {"User-Agent": "Mozilla/5.0"}

# -------------------------------
# Sidebar
# -------------------------------
st.sidebar.header("⚙️ Settings")
max_workers = st.sidebar.slider("Parallel Threads", 5, 30, 15)

# -------------------------------
# File Upload
# -------------------------------
uploaded_file = st.file_uploader("Upload URL File", type=["csv", "xlsx"])
sitemap_url = st.text_input("Optional Sitemap URL")

# -------------------------------
# Helpers
# -------------------------------
def load_file(file):
    return pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)

def normalize(df):
    df.columns = [str(c).lower() for c in df.columns]
    for col in df.columns:
        if col in ["url", "link"]:
            return df[[col]].rename(columns={col: "URL"})
    return df.iloc[:, [0]].rename(columns={df.columns[0]: "URL"})

def enrich(df):
    df["path"] = df["URL"].apply(lambda x: urlparse(x).path)
    df["depth"] = df["path"].apply(lambda x: len([p for p in x.split("/") if p]))
    df["section"] = df["path"].apply(
        lambda x: x.split("/")[1] if len(x.split("/")) > 1 else "root"
    )
    return df

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

    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(fetch, u): i for i, u in enumerate(urls)}

        for i, f in enumerate(as_completed(futures)):
            idx = futures[f]
            s, fu, t = f.result()
            status[idx], final[idx], title[idx] = s, fu, t
            progress.progress((i+1)/len(urls))

    df["status"], df["final_url"], df["title"] = status, final, title
    return df

def get_sitemap(url):
    try:
        r = requests.get(url)
        root = ET.fromstring(r.content)
        return set([e.text for e in root.iter() if "loc" in e.tag])
    except:
        return set()

def compute_metrics(df, sitemap):
    total = len(df)
    dup = total - df["URL"].nunique()
    sections = df["section"].value_counts()

    return {
        "Total Pages": total,
        "% Duplicate": round((dup/total)*100,2) if total else 0,
        "Avg Depth": round(df["depth"].mean(),2),
        "Broken Pages": df[df["status"]>=400].shape[0],
        "Redirects": df[df["status"].between(300,399)].shape[0],
        "Duplicate Titles": df["title"].duplicated().sum() if BS4_AVAILABLE else "N/A",
        "% Orphan Pages": (
            round(len(sitemap - set(df["URL"])) / len(sitemap) * 100,2)
            if sitemap else "N/A"
        )
    }, sections

# -------------------------------
# Report Builders
# -------------------------------
def build_excel(df, metrics, sections):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, "Data", index=False)
        pd.DataFrame(metrics.items(), columns=["Metric","Value"]).to_excel(writer, "Metrics", index=False)
        sections.to_frame("Count").to_excel(writer, "Sections")
    buffer.seek(0)
    return buffer

def build_word(metrics, sections):
    doc = Document()
    doc.add_heading("IA Audit Report", 0)

    doc.add_heading("Metrics", 1)
    for k,v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading("Sections", 1)
    for s,c in sections.items():
        doc.add_paragraph(f"{s}: {c}")

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# -------------------------------
# Main Execution
# -------------------------------
if uploaded_file:
    df = normalize(load_file(uploaded_file)).dropna()
    df = enrich(df)

    st.info("⚡ Running fast crawl...")
    df = crawl(df)

    sitemap = get_sitemap(sitemap_url) if sitemap_url else set()
    metrics, sections = compute_metrics(df, sitemap)

    # -------------------------------
    # UI Tabs
    # -------------------------------
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📁 Data", "⬇️ Reports"])

    with tab1:
        cols = st.columns(len(metrics))
        for i, (k,v) in enumerate(metrics.items()):
            cols[i].metric(k, v)

        st.bar_chart(sections)

    with tab2:
        st.dataframe(df)

    with tab3:
        if EXCEL_AVAILABLE:
            st.download_button("📊 Download Excel Report", build_excel(df, metrics, sections), "IA_Report.xlsx")
        else:
            st.warning("Excel unavailable (install openpyxl)")

        if DOCX_AVAILABLE:
            st.download_button("📄 Download Word Report", build_word(metrics, sections), "IA_Report.docx")
        else:
            st.warning("Word unavailable (install python-docx)")