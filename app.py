import streamlit as st
import pandas as pd

st.set_page_config(page_title="Website Audit Tool", layout="wide")

# -----------------------------
# Utility Functions
# -----------------------------

def normalize_url(url):
    if pd.isna(url):
        return ""
    return url.strip().rstrip('/').lower()


def find_orphans(df):
    if 'url' not in df.columns or 'linked_from' not in df.columns:
        return []

    all_pages = set(df['url'].apply(normalize_url))
    linked_pages = set(df['linked_from'].dropna().apply(normalize_url))

    orphan_pages = all_pages - linked_pages
    return list(orphan_pages)

# -----------------------------
# UI Layout
# -----------------------------

st.title("📊 Website Audit Tool (CSV आधारित)")

st.write("Upload your crawl or URL dataset to generate reports and identify orphan pages.")

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

# -----------------------------
# Processing
# -----------------------------

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)

        st.success("File uploaded successfully!")

        # Normalize URLs
        if 'url' in df.columns:
            df['url'] = df['url'].apply(normalize_url)

        tab1, tab2, tab3 = st.tabs(["Data", "Reports", "Orphan Pages"])

        # -------------------------
        # Tab 1: Data
        # -------------------------
        with tab1:
            st.subheader("Uploaded Data")
            st.dataframe(df)

        # -------------------------
        # Tab 2: Reports
        # -------------------------
        with tab2:
            st.subheader("Summary Report")

            total_pages = len(df)

            col1, col2 = st.columns(2)
            col1.metric("Total Pages", total_pages)
            col2.metric("Columns", len(df.columns))

        # -------------------------
        # Tab 3: Orphan Pages
        # -------------------------
        with tab3:
            st.subheader("Orphan Pages")

            if 'linked_from' not in df.columns:
                st.warning("Column 'linked_from' not found. Unable to calculate orphan pages.")
                st.info("Expected columns: 'url' and 'linked_from'")
            else:
                orphans = find_orphans(df)

                st.write(f"Total Orphan Pages: {len(orphans)}")

                if orphans:
                    orphan_df = pd.DataFrame(orphans, columns=["url"])
                    st.dataframe(orphan_df)
                else:
                    st.info("No orphan pages detected")

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")

else:
    st.info("Please upload a CSV file to begin analysis.")
