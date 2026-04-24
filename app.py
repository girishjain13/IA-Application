import streamlit as st
import pandas as pd
from io import BytesIO
from openpyxl import load_workbook
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
# INFERENCE ENGINE
# -----------------------------
def infer_data(df):
    messages = []

    if 'depth' not in df.columns:
        df['depth'] = df['url'].apply(lambda x: x.count('/'))
        messages.append("Depth inferred")

    if 'in_nav' not in df.columns:
        df['in_nav'] = df['depth'] <= 2
        messages.append("Navigation inferred")

    if 'linked_from' not in df.columns:
        df['linked_from'] = df['url'].apply(
            lambda x: '/'.join(x.split('/')[:-1]) if '/' in x else None
        )
        messages.append("Link relationships inferred")

    return df, messages

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

    # Section classification
    df['section'] = df['url'].apply(lambda x:
        "Doctors" if "doctor" in x else
        "Services" if "service" in x else
        "Locations" if "location" in x else
        "Content" if "blog" in x or "news" in x else
        "Other"
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
# EXCEL (CRASH-PROOF)
# -----------------------------
def generate_excel(df, metrics, section_dist):
    buffer1 = BytesIO()

    try:
        dashboard_df = pd.DataFrame([
            {"Metric": k, "Value": v} for k, v in metrics.items()
        ])

        if section_dist is None or len(section_dist) == 0:
            section_df = pd.DataFrame({"Section": ["No Data"], "Percentage": [0]})
        else:
            section_df = pd.DataFrame({
                "Section": section_dist.index.astype(str),
                "Percentage": section_dist.values
            })

        if df.empty:
            df = pd.DataFrame({"Message": ["No data"]})

        with pd.ExcelWriter(buffer1, engine='openpyxl') as writer:
            dashboard_df.to_excel(writer, "Dashboard", index=False)
            section_df.to_excel(writer, "Sections", index=False)
            df.to_excel(writer, "Raw Data", index=False)

    except Exception as e:
        fallback = pd.DataFrame({"Error": [str(e)]})
        with pd.ExcelWriter(buffer1, engine='openpyxl') as writer:
            fallback.to_excel(writer, "Error", index=False)

    buffer1.seek(0)

    try:
        wb = load_workbook(buffer1)

        if "Sections" in wb.sheetnames:
            ws = wb["Sections"]

            if ws.max_row > 1:
                pie = PieChart()
                data = Reference(ws, min_col=2, min_row=1, max_row=ws.max_row)
                labels = Reference(ws, min_col=1, min_row=2, max_row=ws.max_row)

                pie.add_data(data, titles_from_data=True)
                pie.set_categories(labels)
                pie.title = "Section Distribution"

                ws.add_chart(pie, "E2")

        buffer2 = BytesIO()
        wb.save(buffer2)
        buffer2.seek(0)

        return buffer2

    except Exception:
        return buffer1

# -----------------------------
# UI
# -----------------------------
st.title("📊 IA Audit Tool (Final Version)")

file = st.file_uploader("Upload CSV", type=["csv"])

if file:
    try:
        df = pd.read_csv(file)

        df = auto_map_columns(df)
        df['url'] = df['url'].apply(normalize_url)

        df, msgs = infer_data(df)

        if msgs:
            st.warning(" | ".join(msgs))

        metrics, section_dist = calculate_metrics(df)
        insights = generate_insights(metrics)

        st.subheader("📊 Key Metrics")
        st.json(metrics)

        st.subheader("💡 Insights")
        for i in insights:
            st.write("•", i)

        st.subheader("📄 Data Preview")
        st.dataframe(df)

        st.subheader("📥 Download Reports")

        excel = generate_excel(df, metrics, section_dist)
        st.download_button("Download Excel Dashboard", excel, "IA_Report.xlsx")

        word = generate_word(metrics, insights, section_dist)
        st.download_button("Download Word Report", word, "IA_Report.docx")

    except Exception as e:
        st.error(f"App error: {str(e)}")

else:
    st.info("Upload CSV to begin analysis")