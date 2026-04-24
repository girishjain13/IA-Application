import streamlit as st
import pandas as pd
from io import BytesIO
from docx import Document

st.set_page_config(page_title="IA Audit Tool", layout="wide")

# -----------------------------
# Utility Functions
# -----------------------------

def normalize_url(url):
    if pd.isna(url):
        return ""
    return url.strip().rstrip('/').lower()


def calculate_metrics(df):
    metrics = {}

    metrics['Total Pages'] = len(df)
    metrics['Unique URLs'] = df['url'].nunique() if 'url' in df.columns else 0
    metrics['Duplicate Pages %'] = round((1 - metrics['Unique URLs']/metrics['Total Pages'])*100, 2) if metrics['Total Pages'] else 0

    if 'in_nav' in df.columns:
        metrics['% Pages in Navigation'] = round(df['in_nav'].mean()*100, 2)
        metrics['Pages not in Navigation'] = len(df[df['in_nav'] == False])
    else:
        metrics['% Pages in Navigation'] = 'N/A'
        metrics['Pages not in Navigation'] = 'N/A'

    if 'linked_from' in df.columns:
        all_pages = set(df['url'].apply(normalize_url))
        linked_pages = set(df['linked_from'].dropna().apply(normalize_url))
        orphan_pages = all_pages - linked_pages
        metrics['Orphan Pages'] = len(orphan_pages)
        metrics['% Orphan Pages'] = round((len(orphan_pages)/len(all_pages))*100, 2) if all_pages else 0
    else:
        metrics['Orphan Pages'] = 'N/A'
        metrics['% Orphan Pages'] = 'N/A'

    if 'depth' in df.columns:
        metrics['Avg Depth'] = round(df['depth'].mean(), 2)
        metrics['Max Depth'] = df['depth'].max()
    else:
        metrics['Avg Depth'] = 'N/A'
        metrics['Max Depth'] = 'N/A'

    if 'status' in df.columns:
        metrics['% Error Pages'] = round((len(df[df['status'] != 200])/len(df))*100, 2)
    else:
        metrics['% Error Pages'] = 'N/A'

    if 'owner' in df.columns:
        metrics['Pages without Owner'] = len(df[df['owner'].isna()])
    else:
        metrics['Pages without Owner'] = 'N/A'

    return metrics


def generate_excel(df, metrics):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Raw Data', index=False)
        pd.DataFrame(list(metrics.items()), columns=['Metric','Value']).to_excel(writer, sheet_name='Summary', index=False)
    return output.getvalue()


def generate_word(metrics):
    doc = Document()
    doc.add_heading('IA Audit Report', 0)

    doc.add_heading('Summary Metrics', level=1)
    for k, v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading('Insights', level=1)

    if isinstance(metrics.get('% Orphan Pages'), (int, float)) and metrics['% Orphan Pages'] > 20:
        doc.add_paragraph('High number of orphan pages detected. Improve internal linking.')

    if isinstance(metrics.get('Duplicate Pages %'), (int, float)) and metrics['Duplicate Pages %'] > 10:
        doc.add_paragraph('Significant duplicate content detected. Consider content consolidation.')

    if isinstance(metrics.get('Avg Depth'), (int, float)) and metrics['Avg Depth'] > 4:
        doc.add_paragraph('Navigation depth is high. Simplify navigation structure.')

    output = BytesIO()
    doc.save(output)
    return output.getvalue()

# -----------------------------
# UI
# -----------------------------

st.title("📊 IA Audit & Reporting Tool")

uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    if 'url' in df.columns:
        df['url'] = df['url'].apply(normalize_url)

    metrics = calculate_metrics(df)

    tab1, tab2, tab3 = st.tabs(["Data","Metrics","Download Reports"])

    with tab1:
        st.dataframe(df)

    with tab2:
        st.subheader("IA Metrics")
        for k,v in metrics.items():
            st.write(f"**{k}:** {v}")

    with tab3:
        st.subheader("Download Reports")

        excel_file = generate_excel(df, metrics)
        st.download_button(
            label="Download Excel Report",
            data=excel_file,
            file_name="IA_Audit_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        word_file = generate_word(metrics)
        st.download_button(
            label="Download Word Report",
            data=word_file,
            file_name="IA_Audit_Report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

else:
    st.info("Upload CSV to generate IA audit metrics.")
