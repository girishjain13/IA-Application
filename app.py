import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from io import BytesIO
from docx import Document

st.set_page_config(page_title="IA Audit Tool (Crawler)", layout="wide")

# -----------------------------
# FETCH LINKS (THREAD WORKER)
# -----------------------------
def fetch_links(url, domain):
    links = set()

    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")

        for link in soup.find_all("a", href=True):
            absolute = urljoin(url, link['href'])
            parsed = urlparse(absolute)

            if parsed.netloc == domain:
                clean = parsed.scheme + "://" + parsed.netloc + parsed.path
                links.add(clean)

    except:
        pass

    return url, links


# -----------------------------
# PARALLEL CRAWLER
# -----------------------------
def crawl_site(start_url, max_workers=15):
    visited = set()
    edges = []
    queue = {start_url}

    domain = urlparse(start_url).netloc

    progress = st.empty()

    while queue:
        batch = list(queue)
        queue.clear()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_links, url, domain) for url in batch]

            for future in as_completed(futures):
                url, links = future.result()

                if url in visited:
                    continue

                visited.add(url)

                for link in links:
                    edges.append((url, link))

                    if link not in visited:
                        queue.add(link)

        progress.write(f"🔄 Crawled Pages: {len(visited)}")

    return visited, edges


# -----------------------------
# METRICS ENGINE
# -----------------------------
def calculate_metrics(pages, edges):
    df_edges = pd.DataFrame(edges, columns=["From", "To"])

    linked_pages = set(df_edges["To"])
    orphan_pages = set(pages) - linked_pages

    # Depth calculation (BFS)
    depth_map = {}
    start = list(pages)[0]
    depth_map[start] = 0

    for frm, to in edges:
        if frm in depth_map:
            depth_map[to] = depth_map[frm] + 1

    avg_depth = sum(depth_map.values()) / len(depth_map) if depth_map else 0

    metrics = {
        "Total Pages": len(pages),
        "Total Links": len(edges),
        "Orphan Pages": len(orphan_pages),
        "% Orphan Pages": round((len(orphan_pages)/len(pages))*100, 2) if pages else 0,
        "Avg Depth": round(avg_depth, 2)
    }

    return metrics, orphan_pages, df_edges


# -----------------------------
# INSIGHTS ENGINE
# -----------------------------
def generate_insights(metrics):
    insights = []

    if metrics["% Orphan Pages"] > 30:
        insights.append("High orphan pages indicate weak internal linking structure.")

    if metrics["Avg Depth"] > 4:
        insights.append("Deep navigation increases user effort and impacts UX.")

    if metrics["Total Pages"] > 5000:
        insights.append("Large site size may require structured IA governance.")

    if not insights:
        insights.append("IA structure appears reasonably healthy.")

    return insights


# -----------------------------
# EXCEL REPORT
# -----------------------------
def generate_excel(pages, edges, metrics):
    output = BytesIO()

    df_pages = pd.DataFrame({"Pages": list(pages)})
    df_edges = pd.DataFrame(edges, columns=["From", "To"])
    df_metrics = pd.DataFrame(list(metrics.items()), columns=["Metric", "Value"])

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_metrics.to_excel(writer, sheet_name="Dashboard", index=False)
        df_pages.to_excel(writer, sheet_name="Pages", index=False)
        df_edges.to_excel(writer, sheet_name="Link Graph", index=False)

    output.seek(0)
    return output


# -----------------------------
# WORD REPORT
# -----------------------------
def generate_word(metrics, insights):
    doc = Document()

    doc.add_heading("IA Audit Report", 0)

    doc.add_heading("Executive Summary", 1)
    doc.add_paragraph(
        "This report is based on a full crawl of the website, analyzing link structure and navigation depth."
    )

    doc.add_heading("Metrics", 1)
    for k, v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading("Key Insights", 1)
    for i in insights:
        doc.add_paragraph(f"• {i}")

    doc.add_heading("Recommendations", 1)
    doc.add_paragraph("• Improve internal linking to reduce orphan pages")
    doc.add_paragraph("• Flatten navigation structure")
    doc.add_paragraph("• Introduce structured IA governance")

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# -----------------------------
# UI
# -----------------------------
st.title("🌐 IA Audit Tool (Full Crawler Version)")

url = st.text_input("Enter Website URL (include https://)")

workers = st.slider("Crawl Speed (Threads)", 5, 25, 12)

if st.button("Start Crawl"):

    if not url:
        st.warning("Please enter a URL")
    else:
        with st.spinner("Crawling site..."):
            pages, edges = crawl_site(url, max_workers=workers)

        metrics, orphan_pages, df_edges = calculate_metrics(pages, edges)
        insights = generate_insights(metrics)

        st.subheader("📊 Metrics")
        st.json(metrics)

        st.subheader("💡 Insights")
        for i in insights:
            st.write("•", i)

        st.subheader("⚠️ Orphan Pages")
        st.write(len(orphan_pages))

        st.subheader("📄 Sample Data")
        st.dataframe(df_edges.head(100))

        st.subheader("📥 Download Reports")

        excel = generate_excel(pages, edges, metrics)
        st.download_button("Download Excel Report", excel, "IA_Report.xlsx")

        word = generate_word(metrics, insights)
        st.download_button("Download Word Report", word, "IA_Report.docx")