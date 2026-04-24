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

    if 'in_nav' in df.columns:
        metrics['% Pages in Navigation'] = round(pd.to_numeric(df['in_nav'], errors='coerce').fillna(0).mean()*100, 2)
    else:
        metrics['% Pages in Navigation'] = None

    if 'linked_from' in df.columns:
        all_pages = set(df['url'])
        linked_pages = set(df['linked_from'].dropna())
        orphan_pages = all_pages - linked_pages
        metrics['Orphan Pages'] = len(orphan_pages)
        metrics['% Orphan Pages'] = round((len(orphan_pages)/len(all_pages))*100, 2)
    else:
        metrics['% Orphan Pages'] = None

    if 'depth' in df.columns:
        metrics['Avg Depth'] = round(pd.to_numeric(df['depth'], errors='coerce').mean(), 2)
    else:
        metrics['Avg Depth'] = None

    return metrics, section_dist

# -----------------------------
# Severity Scoring
# -----------------------------

def get_severity(metric, value):
    if value is None:
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
# Excel Dashboard
# -----------------------------

def generate_excel(df, metrics, insights, recs, section_dist):
    output = BytesIO()

    # Build dashboard table
    dashboard_data = []
    for k, v in metrics.items():
        severity = get_severity(k, v) if isinstance(v, (int, float)) else "N/A"
        dashboard_data.append([k, v, severity])

    dashboard_df = pd.DataFrame(dashboard_data, columns=["Metric", "Value", "Severity"])

    section_df = section_dist.reset_index()
    section_df.columns = ['Section', 'Percentage']

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dashboard_df.to_excel(writer, 'Dashboard', index=False)
        section_df.to_excel(writer, 'Sections', index=False)
        pd.DataFrame(insights, columns=['Insights']).to_excel(writer, 'Insights', index=False)
        pd.DataFrame(recs, columns=['Recommendations']).to_excel(writer, 'Recommendations', index=False)
        df.to_excel(writer, 'Raw Data', index=False)

    return output.getvalue()

# -----------------------------
# Word
# -----------------------------

def generate_word(metrics, insights, recs, section_dist):
    doc = Document()
    doc.add_heading('IA Audit Report', 0)

    doc.add_heading('Core Metrics', 1)
    for k, v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading('Insights', 1)
    for i in insights:
        doc.add_paragraph(i)

    doc.add_heading('Recommendations', 1)
    for r in recs:
        doc.add_paragraph(r)

    output = BytesIO()
    doc.save(output)
    return output.getvalue()

# -----------------------------
# UI
# -----------------------------

st.title("📊 IA Audit Tool (Dashboard Ready)")

file = st.file_uploader("Upload CSV", type=['csv'])

if file:
    df = pd.read_csv(file)
    df = auto_map_columns(df)
    df['url'] = df['url'].apply(normalize_url)

    metrics, section_dist = calculate_metrics(df)

    insights = [
        "High duplication may indicate structural inefficiencies.",
        "Deep navigation impacts user journeys.",
        "Orphan pages reduce discoverability."
    ]

    recs = [
        "Adopt entity-driven architecture",
        "Improve internal linking",
        "Flatten navigation structure"
    ]

    tab1, tab2, tab3 = st.tabs(["Data", "Insights", "Download"])

    with tab1:
        st.dataframe(df)

    with tab2:
        for i in insights:
            st.write("•", i)

    with tab3:
        st.download_button("Download Excel Dashboard", generate_excel(df, metrics, insights, recs, section_dist), "IA_Dashboard.xlsx")
        st.download_button("Download Word Report", generate_word(metrics, insights, recs, section_dist), "IA_Report.docx")

else:
    st.info("Upload CSV to start analysis")