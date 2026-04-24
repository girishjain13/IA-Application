import streamlit as st
import pandas as pd
from io import BytesIO
from docx import Document

st.set_page_config(page_title="IA Audit Tool v2", layout="wide")

# -----------------------------
# HELPERS
# -----------------------------
def normalize_url(url):
    if pd.isna(url):
        return ""
    return str(url).strip().rstrip('/').lower()

def auto_map_columns(df):
    df.columns = [col.strip().lower() for col in df.columns]

    for col in df.columns:
        if 'url' in col or 'address' in col:
            df.rename(columns={col: 'url'}, inplace=True)
            break

    if 'url' not in df.columns:
        first_col = df.columns[0]
        df.rename(columns={first_col: 'url'}, inplace=True)
        st.warning(f"No URL column found. Using '{first_col}' as URL.")

    return df

# -----------------------------
# INFERENCE ENGINE
# -----------------------------
def infer_data(df):
    msgs = []

    if 'depth' not in df.columns:
        df['depth'] = df['url'].apply(lambda x: x.count('/'))
        msgs.append("Depth inferred from URL")

    if 'in_nav' not in df.columns:
        df['in_nav'] = df['depth'] <= 2
        msgs.append("Navigation inferred")

    if 'linked_from' not in df.columns:
        df['linked_from'] = df['url'].apply(
            lambda x: '/'.join(x.split('/')[:-1]) if '/' in x else None
        )
        msgs.append("Link relationships inferred")

    return df, msgs

# -----------------------------
# SECTION CLASSIFICATION
# -----------------------------
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
# METRICS ENGINE
# -----------------------------
def calculate_metrics(df):
    df['section'] = df['url'].apply(classify_section)

    total = len(df)
    unique = df['url'].nunique()
    duplicate = total - unique

    section_counts = df['section'].value_counts()
    section_dist = (section_counts / total * 100).round(2)

    nav_pages = df['in_nav'].sum()
    orphan_pages = len(set(df['url']) - set(df['linked_from'].dropna()))

    metrics = {
        "Total Pages": total,
        "Unique Pages": unique,
        "Duplicate Pages": duplicate,
        "Duplicate %": round((duplicate / total) * 100, 2) if total else 0,
        "Pages in Navigation": int(nav_pages),
        "% Pages in Navigation": round((nav_pages / total) * 100, 2),
        "Orphan Pages": orphan_pages,
        "% Orphan Pages": round((orphan_pages / total) * 100, 2),
        "Avg Depth": round(df['depth'].mean(), 2)
    }

    return metrics, section_dist, section_counts

# -----------------------------
# INSIGHT ENGINE (UPGRADED)
# -----------------------------
def generate_insights(metrics, section_dist):
    insights = []

    # Duplication pattern
    if metrics["Duplicate %"] > 50:
        insights.append("High duplication suggests page-level repetition, likely due to entity-based structures (e.g., locations or profiles).")

    # Navigation gap
    if metrics["% Pages in Navigation"] < 60:
        insights.append("Large portion of pages are not accessible via navigation, indicating weak IA structure.")

    # Orphan pages
    if metrics["% Orphan Pages"] > 30:
        insights.append("Significant orphan pages detected, reducing discoverability and SEO performance.")

    # Depth
    if metrics["Avg Depth"] > 4:
        insights.append("Navigation depth is high, increasing user effort to reach key content.")

    # Section imbalance
    if len(section_dist) > 0:
        max_section = section_dist.idxmax()
        max_val = section_dist.max()

        if max_val > 50:
            insights.append(f"{max_section} section dominates ({max_val}%), indicating imbalance in content distribution.")

    if not insights:
        insights.append("IA structure appears balanced with no major structural issues.")

    return insights

# -----------------------------
# EXCEL REPORT (STRUCTURED)
# -----------------------------
def generate_excel(df, metrics, section_dist, section_counts):
    output = BytesIO()

    dashboard_df = pd.DataFrame({
        "Metric": list(metrics.keys()),
        "Value": list(metrics.values())
    })

    section_df = pd.DataFrame({
        "Section": section_counts.index,
        "Pages": section_counts.values,
        "Percentage": section_dist.values
    })

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:

        dashboard_df.to_excel(writer, sheet_name="Dashboard", index=False)
        section_df.to_excel(writer, sheet_name="Section Analysis", index=False)
        df.to_excel(writer, sheet_name="Raw Data", index=False)

        workbook = writer.book

        # Bold header
        bold = workbook.add_format({'bold': True})
        writer.sheets["Dashboard"].set_row(0, None, bold)

    output.seek(0)
    return output

# -----------------------------
# WORD REPORT (CONSULTING STYLE)
# -----------------------------
def generate_word(metrics, insights, section_dist):
    doc = Document()

    doc.add_heading("IA Audit Report", 0)

    # Executive Summary
    doc.add_heading("Executive Summary", 1)
    doc.add_paragraph(
        "This report evaluates the website's information architecture focusing on structure, navigation, and content distribution."
    )

    # Metrics
    doc.add_heading("Core Metrics", 1)
    for k, v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    # Findings
    doc.add_heading("Key Findings", 1)
    for i in insights:
        doc.add_paragraph(f"• {i}")

    # Section Distribution
    doc.add_heading("Section Distribution", 1)
    for sec, val in section_dist.items():
        doc.add_paragraph(f"{sec}: {val}%")

    # Recommendations
    doc.add_heading("Recommendations", 1)
    doc.add_paragraph("• Reduce duplication through reusable content models")
    doc.add_paragraph("• Improve navigation coverage and linking")
    doc.add_paragraph("• Flatten deep navigation structures")
    doc.add_paragraph("• Introduce governance and ownership model")

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# -----------------------------
# UI
# -----------------------------
st.title("📊 IA Audit Tool v2 (Consulting Edition)")

file = st.file_uploader("Upload CSV", type=["csv"])

if file:
    try:
        df = pd.read_csv(file)

        df = auto_map_columns(df)
        df['url'] = df['url'].apply(normalize_url)

        df, msgs = infer_data(df)

        if msgs:
            st.warning(" | ".join(msgs))

        metrics, section_dist, section_counts = calculate_metrics(df)
        insights = generate_insights(metrics, section_dist)

        st.subheader("📊 Metrics")
        st.dataframe(pd.DataFrame(metrics.items(), columns=["Metric", "Value"]))

        st.subheader("💡 Insights")
        for i in insights:
            st.write("•", i)

        st.subheader("📄 Data Preview")
        st.dataframe(df)

        st.subheader("📥 Download Reports")

        excel = generate_excel(df, metrics, section_dist, section_counts)
        st.download_button("Download Excel Dashboard", excel, "IA_Report.xlsx")

        word = generate_word(metrics, insights, section_dist)
        st.download_button("Download Word Report", word, "IA_Report.docx")

    except Exception as e:
        st.error(f"App error: {str(e)}")

else:
    st.info("Upload CSV to start IA audit")