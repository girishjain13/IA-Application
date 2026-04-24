import streamlit as st
import pandas as pd

st.set_page_config(page_title="URL Audit Tool", layout="wide")

st.title("URL Upload & Normalization Tool")

uploaded_file = st.file_uploader(
    "Upload your URL file (CSV or Excel)",
    type=["csv", "xlsx"]
)

# -------------------------------
# File Loader (Handles Excel issue)
# -------------------------------
def load_file(file):
    try:
        if file.name.endswith(".csv"):
            return pd.read_csv(file)

        elif file.name.endswith(".xlsx"):
            try:
                return pd.read_excel(file, engine="openpyxl")
            except ImportError:
                st.error(
                    "Excel support is not enabled (missing 'openpyxl'). "
                    "Please upload a CSV file or update requirements.txt."
                )
                st.stop()

        else:
            st.error("Unsupported file format. Please upload CSV or Excel.")
            st.stop()

    except Exception as e:
        st.error(f"Error reading file: {e}")
        st.stop()


# -------------------------------
# URL Column Normalization
# -------------------------------
def normalize_url_column(df):
    # Clean column names
    df.columns = [str(col).strip().lower() for col in df.columns]

    possible_names = ["url", "urls", "link", "links", "address"]

    # Case 1: Exact match
    for col in df.columns:
        if col in possible_names:
            return df[[col]].rename(columns={col: "URL"})

    # Case 2: Single column file
    if len(df.columns) == 1:
        return df.rename(columns={df.columns[0]: "URL"})

    # Case 3: Detect URL-like content
    for col in df.columns:
        sample = df[col].astype(str).head(10)
        if sample.str.contains("http", case=False, na=False).any():
            return df[[col]].rename(columns={col: "URL"})

    # Case 4: Fallback
    st.warning("No URL column detected. Using first column as URL.")
    return df.iloc[:, [0]].rename(columns={df.columns[0]: "URL"})


# -------------------------------
# Main Execution
# -------------------------------
if uploaded_file:
    df = load_file(uploaded_file)

    st.subheader("Raw Data Preview")
    st.dataframe(df.head())

    df_urls = normalize_url_column(df)

    # Clean URLs
    df_urls["URL"] = df_urls["URL"].astype(str).str.strip()
    df_urls = df_urls[df_urls["URL"] != ""]
    df_urls = df_urls.dropna()

    st.subheader("Normalized URL Data")
    st.dataframe(df_urls.head())

    st.success(f"Processed {len(df_urls)} URLs successfully")

    # Download cleaned file
    csv = df_urls.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Cleaned URLs",
        csv,
        "cleaned_urls.csv",
        "text/csv"
    )