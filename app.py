import streamlit as st
import pandas as pd
from io import BytesIO
from docx import Document

st.set_page_config(page_title="IA Audit Tool", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
def normalize_url(url):
    if pd.isna(url):
        return ""
    return str(url).strip().rstrip('/').lower()

def auto_map_columns(df):
    df.columns = [col.strip().lower() for col in df.columns]
    mapping = {}

    for col in df.columns:
        if 'url' in col or 'address' in col:
            mapping[col] = 'url'
        elif 'link' in col:
            mapping[col] = 'linked_from'
        elif 'nav' in col:
            mapping[col] = 'in_nav'
        elif 'depth' in col or 'level' in col:
            mapping[col] = 'depth'
        elif 'status' in col:
            mapping[col] = 'status'
        elif 'owner' in col:
            mapping[col] = 'owner'

    df.rename(columns=mapping, inplace=True)

    if 'url' not in df.columns:
        original_col = df.columns[0]
        df.rename(columns={original_col: 'url'}, inplace=True)
        st.warning(f"No URL column found. Using '{original_col}' as URL.")

    return df

def classify_section(url):
    if "doctor" in url:
        return "Doctors"
    elif "service" in url:
        return "Services"
    elif "location" in url:
        return "Locations"
    elif "blog" in url or "news" in url:
        return "Content"
    return "Other"

# -----------------------------
# Metrics
# -----------------------------
def calculate_metrics(df):
    metrics = {}

    metrics['Total Pages'] = len(df)
    metrics['Unique URLs'] = df['url'].nunique()
    metrics['Duplicate Pages %'] = round((1 - metrics['Unique URLs']/metrics['Total Pages'])*100, 2)

    df['section'] = df['url'].apply(classify_section)
    section_dist = (df['section'].value_counts(normalize=True)*100).round(2)

    metrics['% Pages in Navigation'] = None
    metrics['% Orphan Pages'] = None
    metrics['Avg Depth'] = None

    if 'in_nav' in df.columns:
        metrics['% Pages in Navigation'] = round(pd.to_numeric(df['in_nav'], errors='coerce').fillna(0).mean()*100, 2)

    if 'linked_from' in df.columns:
        all_pages = set(df['url'])
        linked_pages = set(df['linked_from'].dropna())
        orphan_pages = all_pages - linked_pages
        metrics['% Orphan Pages'] = round((len(orphan_pages)/len(all_pages))*100, 2)

    if 'depth' in df.columns:
        metrics['Avg Depth'] = round(pd.to_numeric(df['depth'], errors='coerce').mean(), 2)

    return metrics, section_dist

# -----------------------------
# Severity
# -----------------------------
def get_severity(metric, value):
    if value is None or not isinstance(value, (int, float)):
        return "N/A"

    if "Duplicate" in metric:
        return "High" if value > 50 else "Medium" if value > 20 else "Low"

    if "Orphan" in metric:
        return "High" if value > 30 else "Medium" if value > 10 else "Low"

    if "Depth" in metric:
        return "High" if value > 4 else "Medium" if value > 3 else "Low"

    if "Navigation" in metric:
        return "High" if value < 50 else "Medium" if value < 70 else "Low"

    return "Low"

# -----------------------------
# Excel (FULLY FIXED)
# -----------------------------
def generate_excel(df, metrics, section_dist):
    output = BytesIO()

    # Safe dashboard creation
    dashboard_rows = []
    for k, v in metrics.items():
        safe_value = v if v is not None else "N/A"
        severity = get_severity(k, v)
        dashboard_rows.append({
            "Metric": k,
            "Value": safe_value,
            "Severity": severity
        })

    dashboard_df = pd.DataFrame(dashboard_rows)

    # Safe section df
    section_df = section_dist.reset_index()
    section_df.columns = ['Section', 'Percentage']

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dashboard_df.to_excel(writer, 'Dashboard', index=False)
        section_df.to_excel(writer, 'Sections', index=False)
        df.to_excel(writer, 'Raw Data', index=False)

    return output.getvalue()

# -----------------------------
# Word
# -----------------------------
def generate_word(metrics):
    doc = Document()
    doc.add_heading('IA Audit Report', 0)

    for k, v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    output = BytesIO()
    doc.save(output)
    return output.getvalue()

# -----------------------------
# UI
# -----------------------------
st.title("📊 IA Audit Tool (Stable Dashboard Version)")

file = st.file_uploader("Upload CSV", type=['csv'])

if file:
    df = pd.read_csv(file)
    df = auto_map_columns(df)
    df['url'] = df['url'].apply(normalize_url)

    metrics, section_dist = calculate_metrics(df)

    tab1, tab2 = st.tabs(["Data", "Download"])

    with tab1:
        st.dataframe(df)

    with tab2:
        st.download_button(
            "Download Excel Dashboard",
            generate_excel(df, metrics, section_dist),
            "IA_Dashboard.xlsx"
        )

        st.download_button(
            "Download Word Report",
            generate_word(metrics),
            "IA_Report.docx"
        )

else:
    st.info("Upload CSV to start analysis")