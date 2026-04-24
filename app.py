import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
from collections import deque
from io import BytesIO
from docx import Document

st.set_page_config(layout="wide")

# -----------------------------
# CRAWLER (NO HARD LIMIT)
# -----------------------------
def crawl_site(start_url):
    visited = set()
    edges = []
    queue = deque([start_url])

    domain = urlparse(start_url).netloc

    while queue:
        url = queue.popleft()

        if url in visited:
            continue

        visited.add(url)

        try:
            res = requests.get(url, timeout=5)
            soup = BeautifulSoup(res.text, "html.parser")

            for link in soup.find_all("a", href=True):
                absolute = urljoin(url, link['href'])
                parsed = urlparse(absolute)

                # stay within domain
                if parsed.netloc != domain:
                    continue

                clean_url = parsed.scheme + "://" + parsed.netloc + parsed.path

                edges.append((url, clean_url))

                if clean_url not in visited:
                    queue.append(clean_url)

        except:
            continue

    return visited, edges

# -----------------------------
# METRICS
# -----------------------------
def calculate_metrics(pages, edges):
    df_edges = pd.DataFrame(edges, columns=["from", "to"])

    linked_pages = set(df_edges['to'])
    orphan_pages = set(pages) - linked_pages

    depths = {list(pages)[0]: 0}

    # BFS depth calc
    for frm, to in edges:
        if frm in depths:
            depths[to] = depths[frm] + 1

    avg_depth = sum(depths.values()) / len(depths) if depths else 0

    metrics = {
        "Total Pages": len(pages),
        "Orphan Pages": len(orphan_pages),
        "% Orphan Pages": round((len(orphan_pages)/len(pages))*100,2),
        "Avg Depth": round(avg_depth,2)
    }

    return metrics, orphan_pages

# -----------------------------
# WORD REPORT
# -----------------------------
def generate_word(metrics):
    doc = Document()
    doc.add_heading("IA Audit Report", 0)

    for k, v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# -----------------------------
# UI
# -----------------------------
st.title("🌐 Full Site IA Crawler")

url = st.text_input("Enter Website URL")

if st.button("Start Crawl"):

    with st.spinner("Crawling entire site... this may take time"):

        pages, edges = crawl_site(url)
        metrics, orphan_pages = calculate_metrics(pages, edges)

    st.subheader("📊 Metrics")
    st.json(metrics)

    st.subheader("🔗 Total Pages Crawled")
    st.write(len(pages))

    st.subheader("⚠️ Orphan Pages")
    st.write(len(orphan_pages))

    word = generate_word(metrics)

    st.download_button("Download Report", word, "IA_Report.docx")