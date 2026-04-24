import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import time

st.set_page_config(page_title="Website Audit Tool", layout="wide")

# -----------------------------
# Utility Functions
# -----------------------------

def normalize_url(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/').lower()


def crawl_site(start_url, max_pages=50):
    visited = set()
    to_visit = [start_url]
    data = []

    domain = urlparse(start_url).netloc

    progress = st.progress(0)
    status_text = st.empty()

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        url = normalize_url(url)

        if url in visited:
            continue

        status_text.text(f"Crawling: {url}")

        try:
            headers = {
                "User-Agent": "Mozilla/5.0"
            }

            response = requests.get(url, timeout=10, headers=headers)
            visited.add(url)

            soup = BeautifulSoup(response.text, "html.parser")
            links = []

            for a in soup.find_all("a", href=True):
                link = urljoin(url, a["href"])
                parsed = urlparse(link)

                if parsed.netloc == domain:
                    clean_link = normalize_url(link)

                    if clean_link not in links:
                        links.append(clean_link)

                    if clean_link not in visited and clean_link not in to_visit:
                        to_visit.append(clean_link)

            title = soup.title.string.strip() if soup.title and soup.title.string else ""

            data.append({
                "url": url,
                "status": response.status_code,
                "title": title,
                "internal_links": links,
                "link_count": len(links)
            })

        except Exception as e:
            data.append({
                "url": url,
                "status": "error",
                "title": "",
                "internal_links": [],
                "link_count": 0
            })

        progress.progress(len(visited) / max_pages)
        time.sleep(0.5)  # prevent aggressive crawling

    status_text.text("Crawling complete")

    return pd.DataFrame(data)


def find_orphans(df):
    all_pages = set(df['url'])
    linked_pages = set()

    for links in df['internal_links']:
        linked_pages.update(links)

    return list(all_pages - linked_pages)


# -----------------------------
# UI Layout
# -----------------------------

st.title("🌐 Website Audit & Crawler Tool")

with st.sidebar:
    st.header("Crawl Settings")
    start_url = st.text_input("Website URL", placeholder="https://example.com")
    max_pages = st.slider("Max Pages to Crawl", 10, 200, 50)
    start_crawl = st.button("Start Crawl")

# Session state
if "data" not in st.session_state:
    st.session_state.data = None

# -----------------------------
# Crawl Execution
# -----------------------------

if start_crawl and start_url:
    if not start_url.startswith("http"):
        st.error("Please enter a valid URL starting with http or https")
    else:
        with st.spinner("Crawling website..."):
            df = crawl_site(start_url, max_pages)
            st.session_state.data = df
        st.success("Crawl completed!")

# -----------------------------
# Tabs
# -----------------------------

if st.session_state.data is not None:
    df = st.session_state.data

    tab1, tab2, tab3, tab4 = st.tabs(["Crawled Data", "Reports", "Orphan Pages", "Errors"])

    # Tab 1
    with tab1:
        st.subheader("Crawled Pages")
        st.dataframe(df)

    # Tab 2
    with tab2:
        st.subheader("Summary Report")

        total_pages = len(df)
        error_pages = len(df[df['status'] != 200])
        avg_links = df['link_count'].mean()

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Pages", total_pages)
        col2.metric("Error Pages", error_pages)
        col3.metric("Avg Internal Links", round(avg_links, 2) if not pd.isna(avg_links) else 0)

    # Tab 3
    with tab3:
        st.subheader("Orphan Pages")

        orphans = find_orphans(df)

        st.write(f"Total Orphan Pages: {len(orphans)}")

        if orphans:
            orphan_df = pd.DataFrame(orphans, columns=["url"])
            st.dataframe(orphan_df)
        else:
            st.info("No orphan pages detected")

    # Tab 4
    with tab4:
        st.subheader("Error Pages")

        error_df = df[df['status'] != 200]

        if not error_df.empty:
            st.dataframe(error_df)
        else:
            st.info("No errors found")

else:
    st.info("Enter a URL and start crawling to see results.")
