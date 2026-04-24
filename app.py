import streamlit as st
import pandas as pd
from io import BytesIO
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
    metrics['Duplicate Pages %'] = round((1 - unique/total)*100, 2) if total else 0
    metrics['% Pages in Navigation'] = round(df['in_nav'].astype(int).mean()*100, 2)

    all_pages = set(df['url'])
    linked = set(df['linked_from'].dropna())
    orphan = all_pages - linked

    metrics['% Orphan Pages'] = round((len(orphan)/len(all_pages))*100, 2) if all_pages else 0
    metrics['Avg Depth'] = round(df['depth'].mean(), 2)

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
# INSIGHTS
# -----------------------------
def generate_insights(metrics):
    insights = []

    if metrics['Duplicate Pages %'] > 50:
        insights.append("High duplication indicates inefficient IA structure.")

    if metrics['% Orphan Pages'] > 30:
        insights.append("High orphan pages reduce discoverability.")

    if metrics['Avg Depth'] > 4:
        insights.append("Deep navigation impacts usability.")

    if metrics['% Pages in Navigation'] < 60:
        insights.append("Low navigation coverage suggests poor IA.")

    if not insights:
        insights.append("IA structure appears healthy.")

    return insights

# -----------------------------
# WORD REPORT
# -----------------------------
def generate_word(metrics, insights, section_dist):
    doc = Document()
    doc.add_heading('IA Audit Report', 0)

    doc.add_heading('1. Overview', 1)
    doc.add_paragraph("This report evaluates the website information architecture.")

    doc.add_heading('2. Metrics', 1)
    for k, v in metrics.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading('3. Section Distribution', 1)
    for sec, val in section_dist.items():
        doc.add_paragraph(f"{sec}: {val}%")

    doc.add_heading('4. Insights', 1)
    for i in insights:
        doc.add_paragraph(f"• {i}")

    doc.add_heading('5. Recommendations', 1)
    doc.add_paragraph("• Reduce duplication via structured content models")
    doc.add_paragraph("• Improve internal linking")
    doc.add_paragraph("• Simplify navigation hierarchy")

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# -----------------------------
# EXCEL (XLSXWRITER ONLY)
# -----------------------------
def generate_excel(df, metrics, section_dist):
    output = BytesIO()

    df = df.astype(str)

    dashboard_df = pd.DataFrame({
        "Metric": list(metrics.keys()),
        "Value": [str(v) for v in metrics.values()]
    })

    if section_dist is None or len(section_dist) == 0:
        section_df = pd.DataFrame({
            "Section": ["No Data"],
            "Percentage": [0]
        })
    else:
        section_df = pd.DataFrame({
            "Section": list(section_dist.index),
            "Percentage": list(section_dist.values)
        })

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:

        # Always create first sheet
        pd.DataFrame({"Status": ["IA Report Generated"]}).to_excel(
            writer, sheet_name="Summary", index=False
        )

        dashboard_df.to_excel(writer, sheet_name="Metrics", index=False)
        section_df.to_excel(writer, sheet_name="Sections", index=False)
        df.to_excel(writer, sheet_name="Raw Data", index=False)

        # Basic formatting
        workbook  = writer.book
        worksheet = writer.sheets['Metrics']

        bold = workbook.add_format({'bold': True})
        worksheet.set_row(0, None, bold)

    output.seek(0)
    return output

# -----------------------------
# UI
# -----------------------------
st.title("📊 IA Audit Tool (Final Stable Version)")

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

        st.subheader("📊 Metrics")
        st.json(metrics)

        st.subheader("💡 Insights")
        for i in insights:
            st.write("•", i)

        st.subheader("📄 Data Preview")
        st.dataframe(df)

        st.subheader("📥 Download Reports")

        excel = generate_excel(df, metrics, section_dist)
        st.download_button(
            "Download Excel Report",
            data=excel,
            file_name="IA_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        word = generate_word(metrics, insights, section_dist)
        st.download_button(
            "Download Word Report",
            data=word,
            file_name="IA_Report.docx"
        )

    except Exception as e:
        st.error(f"App error: {str(e)}")

else:
    st.info("Upload CSV to begin analysis")