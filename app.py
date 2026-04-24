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
        elif 'link' in col or 'inlink' in col:
            mapping[col] = 'linked_from'
        elif 'nav' in col:
            mapping[col] = 'in_nav'
        elif 'depth' in col or 'level' in col:
            mapping[col] = 'depth'
        elif 'status' in col or 'code' in col:
            mapping[col] = 'status'
        elif 'owner' in col:
            mapping[col] = 'owner'

    df.rename(columns=mapping, inplace=True)

    # Fallback for URL
    if 'url' not in df.columns:
        df.rename(columns={df.columns[0]: 'url'}, inplace=True)
        st.warning(f"No URL column found. Using '{df.columns[0]}' as URL.")

    return df


def classify_section(url):
    url = url.lower()
    if "doctor" in url:
        return "Doctors"
    elif "service" in url:
        return "Services"
    elif "location" in url:
        return "Locations"
    elif "blog" in url or "news" in url:
        return "Content"
    else:
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
        metrics['% Pages in Navigation'] = 'N/A'

    if 'linked_from' in df.columns:
        all_pages = set(df['url'])
        linked_pages = set(df['linked_from'].dropna())
        orphan_pages = all_pages - linked_pages
        metrics['Orphan Pages'] = len(orphan_pages)
        metrics['% Orphan Pages'] = round((len(orphan_pages)/len(all_pages))*100, 2)
    else:
        metrics['Orphan Pages'] = 'N/A'
        metrics['% Orphan Pages'] = 'N/A'

    if 'depth' in df.columns:
        metrics['Avg Depth'] = round(pd.to_numeric(df['depth'], errors='coerce').mean(), 2)
    else:
        metrics['Avg Depth'] = 'N/A'

    if 'status' in df.columns:
        metrics['% Error Pages'] = round((len(df[pd.to_numeric(df['status'], errors='coerce') != 200])/len(df))*100, 2)
    else:
        metrics['% Error Pages'] = 'N/A'

    if 'owner' in df.columns:
        metrics['Pages without Owner'] = len(df[df['owner'].isna()])
    else:
        metrics['Pages without Owner'] = 'N/A'

    return metrics, section_dist

# -----------------------------
# Insights
# -----------------------------

def generate_insights(metrics, section_dist):
    insights = []

    if metrics['Duplicate Pages %'] > 50:
        insights.append("High duplication indicates structural repetition (likely location-based IA).")

    if isinstance(metrics.get('% Orphan Pages'), (int,float)) and metrics['% Orphan Pages'] > 30:
        insights.append("High orphan pages suggest weak internal linking.")

    if isinstance(metrics.get('Avg Depth'), (int,float)) and metrics['Avg Depth'] > 4:
        insights.append("Deep navigation increases user effort.")

    if isinstance(metrics.get('% Pages in Navigation'), (int,float)) and metrics['% Pages in Navigation'] != 'N/A' and metrics['% Pages in Navigation'] < 60:
        insights.append("Low navigation coverage indicates fragmented IA.")

    if 'Doctors' in section_dist and section_dist['Doctors'] > 40:
        insights.append("Doctor section dominates IA, causing duplication.")

    return insights

# -----------------------------
# Recommendations
# -----------------------------

def generate_recommendations(metrics):
    recs = []

    if metrics['Duplicate Pages %'] > 50:
        recs.append("Move to entity-driven architecture.")

    if isinstance(metrics.get('% Orphan Pages'), (int,float)) and metrics['% Orphan Pages'] > 30:
        recs.append("Improve internal linking.")

    if isinstance(metrics.get('Avg Depth'), (int,float)) and metrics['Avg Depth'] > 4:
        recs.append("Flatten navigation structure.")

    recs.append("Implement governance and taxonomy model.")

    return recs

# -----------------------------
# Excel
# -----------------------------

def generate_excel(df, metrics, insights, recs, section_dist):
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(list(metrics.items()), columns=['Metric','Value']).to_excel(writer, 'Summary', index=False)
        section_dist.reset_index().rename(columns={'index':'Section','section':'%'}).to_excel(writer, 'Sections', index=False)
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
    for k,v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading('Section Distribution', 1)
    for sec, val in section_dist.items():
        doc.add_paragraph(f"{sec}: {val}%")

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

st.title("📊 IA Audit Tool (Schema-Agnostic)")

file = st.file_uploader("Upload CSV", type=['csv'])

if file:
    df = pd.read_csv(file)

    df = auto_map_columns(df)

    df['url'] = df['url'].apply(normalize_url)

    metrics, section_dist = calculate_metrics(df)
    insights = generate_insights(metrics, section_dist)
    recs = generate_recommendations(metrics)

    tab1, tab2, tab3 = st.tabs(["Data","Insights","Download"])

    with tab1:
        st.dataframe(df)

    with tab2:
        for i in insights:
            st.write("•", i)

    with tab3:
        st.download_button("Download Excel", generate_excel(df, metrics, insights, recs, section_dist), "IA_Report.xlsx")
        st.download_button("Download Word", generate_word(metrics, insights, recs, section_dist), "IA_Report.docx")

else:
    st.info("Upload CSV to start analysis")