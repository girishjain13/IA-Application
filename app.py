import streamlit as st
import pandas as pd
from io import BytesIO
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from openpyxl.chart import PieChart, Reference
from docx import Document

st.set_page_config(page_title="IA Audit Tool", layout="wide")

# -----------------------------
# HELPERS
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
        elif 'depth' in col:
            mapping[col] = 'depth'

    df.rename(columns=mapping, inplace=True)

    if 'url' not in df.columns:
        original = df.columns[0]
        df.rename(columns={original: 'url'}, inplace=True)
        st.warning(f"No URL column found. Using '{original}' as URL.")

    return df

# -----------------------------
# INFERENCE
# -----------------------------
def infer_data(df):
    msgs = []

    if 'depth' not in df.columns:
        df['depth'] = df['url'].apply(lambda x: x.count('/'))
        msgs.append("Depth inferred")

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
# METRICS
# -----------------------------
def calculate_metrics(df):
    metrics = {}

    total = len(df)
    unique = df['url'].nunique()

    metrics['Total Pages'] = total
    metrics['Duplicate %'] = round((1 - unique/total)*100,2) if total else 0
    metrics['Navigation %'] = round(df['in_nav'].astype(int).mean()*100,2)

    all_pages = set(df['url'])
    linked = set(df['linked_from'].dropna())
    orphan = all_pages - linked

    metrics['Orphan %'] = round((len(orphan)/len(all_pages))*100,2) if all_pages else 0
    metrics['Avg Depth'] = round(df['depth'].mean(),2)

    df['section'] = df['url'].apply(lambda x:
        "Doctors" if "doctor" in x else
        "Services" if "service" in x else
        "Locations" if "location" in x else
        "Content" if "blog" in x else "Other"
    )

    section_dist = (df['section'].value_counts(normalize=True)*100).round(2)

    return metrics, section_dist

# -----------------------------
# INSIGHTS ENGINE
# -----------------------------
def generate_insights(metrics):
    insights = []

    if metrics['Duplicate %'] > 50:
        insights.append("High duplication indicates structural inefficiencies.")

    if metrics['Orphan %'] > 30:
        insights.append("Large number of orphan pages reduces discoverability.")

    if metrics['Avg Depth'] > 4:
        insights.append("Deep navigation increases user effort.")

    if metrics['Navigation %'] < 60:
        insights.append("Low navigation coverage suggests fragmented IA.")

    return insights

# -----------------------------
# WORD REPORT
# -----------------------------
def generate_word(metrics, insights, section_dist):
    doc = Document()

    doc.add_heading('Website IA Audit Report', 0)

    doc.add_heading('1. Overview', 1)
    doc.add_paragraph("This report provides an analysis of the website's information architecture.")

    doc.add_heading('2. Core Metrics', 1)
    for k, v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading('3. Section Distribution', 1)
    for sec, val in section_dist.items():
        doc.add_paragraph(f"{sec}: {val}%")

    doc.add_heading('4. Key Insights', 1)
    for i in insights:
        doc.add_paragraph(f"- {i}")

    doc.add_heading('5. Recommendations', 1)
    doc.add_paragraph("• Reduce duplication via entity-based architecture")
    doc.add_paragraph("• Improve internal linking")
    doc.add_paragraph("• Flatten navigation depth")
    doc.add_paragraph("• Introduce governance model")

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# -----------------------------
# EXCEL
# -----------------------------
def generate_excel(df, metrics, section_dist):
    buffer1 = BytesIO()

    dashboard = pd.DataFrame([
        {"Metric": k, "Value": v} for k,v in metrics.items()
    ])

    section_df = pd.DataFrame({
        "Section": section_dist.index,
        "Percentage": section_dist.values
    })

    with pd.ExcelWriter(buffer1, engine='openpyxl') as writer:
        dashboard.to_excel(writer, "Dashboard", index=False)
        section_df.to_excel(writer, "Sections", index=False)
        df.to_excel(writer, "Raw Data", index=False)

    buffer1.seek(0)

    wb = load_workbook(buffer1)

    # chart
    if len(section_df) > 0:
        ws = wb["Sections"]
        pie = PieChart()

        data = Reference(ws, min_col=2, min_row=1, max_row=len(section_df)+1)
        labels = Reference(ws, min_col=1, min_row=2, max_row=len(section_df)+1)

        pie.add_data(data, titles_from_data=True)
        pie.set_categories(labels)
        pie.title = "Section Distribution"

        ws.add_chart(pie, "E2")

    buffer2 = BytesIO()
    wb.save(buffer2)
    buffer2.seek(0)

    return buffer2

# -----------------------------
# UI
# -----------------------------
st.title("📊 IA Audit Tool (Interactive)")

file = st.file_uploader("Upload CSV", type=["csv"])

if file:
    df = pd.read_csv(file)

    df = auto_map_columns(df)
    df['url'] = df['url'].apply(normalize_url)

    df, msgs = infer_data(df)

    if msgs:
        st.warning(" | ".join(msgs))

    # 🔹 USER INPUT CONTROLS
    st.sidebar.header("⚙️ Analysis Settings")
    depth_threshold = st.sidebar.slider("Depth Threshold", 2, 6, 4)
    orphan_threshold = st.sidebar.slider("Orphan Threshold %", 10, 60, 30)

    metrics, section_dist = calculate_metrics(df)
    insights = generate_insights(metrics)

    # 🔹 DISPLAY METRICS
    st.subheader("📊 Key Metrics")
    st.json(metrics)

    # 🔹 DISPLAY INSIGHTS
    st.subheader("💡 Insights")
    for i in insights:
        st.write("•", i)

    # 🔹 DATA VIEW
    st.subheader("📄 Data Preview")
    st.dataframe(df)

    # 🔹 DOWNLOADS
    st.subheader("📥 Download Reports")

    excel = generate_excel(df, metrics, section_dist)
    st.download_button("Download Excel Dashboard", excel, "IA_Report.xlsx")

    word = generate_word(metrics, insights, section_dist)
    st.download_button("Download Word Report", word, "IA_Report.docx")

else:
    st.info("Upload CSV to begin analysis")