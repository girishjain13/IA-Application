import streamlit as st
import pandas as pd

st.set_page_config(page_title="URL Audit Tool", layout="wide")

st.title("URL Upload & Normalization")

uploaded_file = st.file_uploader(
    "Upload your URL file (CSV or Excel)",
    type=["csv", "xlsx"]
)

def load_file(file):
    try:
        if file.name.endswith(".csv"):
            return pd.read_csv(file)
        else:
            return pd.read_excel(file)
    except Exception as e:
        st.error(f"Error reading file: {e}")
        st.stop()

def normalize_url_column(df):
    # Clean column names
    df.columns = [str(col).strip().lower() for col in df.columns]

    # Common URL column name patterns
    possible_names = ["url", "urls", "link", "links", "address"]

    # Case 1: Direct match
    for col in df.columns:
        if col in possible_names:
            return df[[col]].rename(columns={col: "URL"})

    # Case 2: Single column file
    if len(df.columns) == 1:
        return df.rename(columns={df.columns[0]: "URL"})

    # Case 3: Try detecting column with URLs
    for col in df.columns:
        sample_values = df[col].astype(str).head(10)
        if sample_values.str.contains("http").any():
            return df[[col]].rename(columns={col: "URL"})

    # Case 4: fallback → take first column
    st.warning("No explicit URL column found. Using first column as URL.")
    return df.iloc[:, [0]].rename(columns={df.columns[0]: "URL"})


if uploaded_file:
    df = load_file(uploaded_file)

    st.write("### Raw Data Preview")
    st.dataframe(df.head())

    df_urls = normalize_url_column(df)

    # Final cleanup
    df_urls["URL"] = df_urls["URL"].astype(str).str.strip()
    df_urls = df_urls[df_urls["URL"] != ""]
    df_urls = df_urls.dropna()

    st.write("### Normalized URL Data")
    st.dataframe(df_urls.head())

    st.success(f"Successfully processed {len(df_urls)} URLs")

    # Optional download
    csv = df_urls.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Cleaned URLs",
        csv,
        "cleaned_urls.csv",
        "text/csv"
    )