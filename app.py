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
    return url.strip().rstrip('/').lower()


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
# Metrics Engine
# -----------------------------

def calculate_metrics(df):
    metrics = {}

    metrics['Total Pages'] = len(df)
    metrics['Unique URLs'] = df['url'].nunique()
    metrics['Duplicate Pages %'] = round((1 - metrics['Unique URLs']/metrics['Total Pages'])*100, 2)

    # Sections
    df['section'] = df['url'].apply(classify_section)
    section_dist = (df['section'].value_counts(normalize=True)*100).round(2)

    # Navigation
    if 'in_nav' in df.columns:
        metrics['% Pages in Navigation'] = round(df['in_nav'].mean()*100, 2)
        metrics['Pages not in Navigation'] = len(df[df['in_nav'] == False])
    else:
        metrics['% Pages in Navigation'] = 'N/A'

    # Orphans
    if 'linked_from' in df.columns:
        all_pages = set(df['url'])
        linked_pages = set(df['linked_from'].dropna())
        orphan_pages = all_pages - linked_pages
        metrics['Orphan Pages'] = len(orphan_pages)
        metrics['% Orphan Pages'] = round((len(orphan_pages)/len(all_pages))*100, 2)
    else:
        metrics['Orphan Pages'] = 'N/A'
        metrics['% Orphan Pages'] = 'N/A'

    # Depth
    if 'depth' in df.columns:
        metrics['Avg Depth'] = round(df['depth'].mean(), 2)
    else:
        metrics['Avg Depth'] = 'N/A'

    return metrics, section_dist

# -----------------------------
# Insights Engine
# -----------------------------

def generate_insights(metrics, section_dist):
    insights = []

    if metrics['Duplicate Pages %'] > 50:
        insights.append("High duplication driven by structural repetition (likely location-based architecture).")

    if isinstance(metrics.get('% Orphan Pages'), (int,float)) and metrics['% Orphan Pages'] > 30:
        insights.append("Large number of orphan pages indicates weak internal linking.")

    if isinstance(metrics.get('Avg Depth'), (int,float)) and metrics['Avg Depth'] > 4:
        insights.append("Deep navigation increases user effort and reduces discoverability.")

    if isinstance(metrics.get('% Pages in Navigation'), (int,float)) and metrics['% Pages in Navigation'] < 60:
        insights.append("Low navigation coverage suggests fragmented IA.")

    # Section imbalance
    if 'Doctors' in section_dist and section_dist['Doctors'] > 40:
        insights.append("Doctor section dominates IA, indicating duplication across entities.")

    return insights

# -----------------------------
# Recommendations
# -----------------------------

def generate_recommendations(metrics):
    recs = []

    if metrics['Duplicate Pages %'] > 50:
        recs.append("Move to entity-driven architecture (Doctors, Services, Locations).")

    if isinstance(metrics.get('% Orphan Pages'), (int,float)) and metrics['% Orphan Pages'] > 30:
        recs.append("Improve internal linking and navigation pathways.")

    if isinstance(metrics.get('Avg Depth'), (int,float)) and metrics['Avg Depth'] > 4:
        recs.append("Flatten navigation to reduce clicks.")

    recs.append("Implement centralized content governance and taxonomy.")

    return recs

# -----------------------------
# Excel Generator
# -----------------------------

def generate_excel(df, metrics, insights, recs, section_dist):
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:

        # Summary
        summary = pd.DataFrame(list(metrics.items()), columns=['Metric','Value'])
        summary.to_excel(writer, sheet_name='Summary', index=False)

        # Section Distribution
        section_dist.reset_index().rename(columns={'index':'Section','section':'%'}).to_excel(writer, sheet_name='Sections', index=False)

        # Insights
        pd.DataFrame(insights, columns=['Insights']).to_excel(writer, sheet_name='Insights', index=False)

        # Recommendations
        pd.DataFrame(recs, columns=['Recommendations']).to_excel(writer, sheet_name='Recommendations', index=False)

        # Raw
        df.to_excel(writer, sheet_name='Raw Data', index=False)

    return output.getvalue()

# -----------------------------
# Word Generator
# -----------------------------

def generate_word(metrics, insights, recs, section_dist):
    doc = Document()

    doc.add_heading('Website Information Architecture Audit Report', 0)

    doc.add_heading('Core Metrics', 1)
    for k,v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading('Section Distribution', 1)
    for sec, val in section_dist.items():
        doc.add_paragraph(f"{sec}: {val}%")

    doc.add_heading('Key Insights', 1)
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

st.title("📊 IA Audit Tool (Consulting Grade)")

file = st.file_uploader("Upload CSV", type=['csv'])

if file:
    df = pd.read_csv(file)

    df['url'] = df['url'].apply(normalize_url)

    metrics, section_dist = calculate_metrics(df)
    insights = generate_insights(metrics, section_dist)
    recs = generate_recommendations(metrics)

    tab1, tab2, tab3 = st.tabs(["Data","Insights","Download"])

    with tab1:
        st.dataframe(df)

    with tab2:
        st.subheader("Insights")
        for i in insights:
            st.write("•", i)

    with tab3:
        excel = generate_excel(df, metrics, insights, recs, section_dist)
        st.download_button("Download Excel", excel, "IA_Report.xlsx")

        word = generate_word(metrics, insights, recs, section_dist)
        st.download_button("Download Word", word, "IA_Report.docx")

else:
    st.info("Upload CSV to start analysis")
