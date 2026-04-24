import streamlit as st
import pandas as pd
from io import BytesIO
from docx import Document
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from openpyxl.chart import PieChart, Reference

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

    df.rename(columns=mapping, inplace=True)

    if 'url' not in df.columns:
        df.rename(columns={df.columns[0]: 'url'}, inplace=True)
        st.warning(f"No URL column found. Using '{df.columns[0]}' as URL.")

    return df

# -----------------------------
# INFERENCE ENGINE (NEW)
# -----------------------------
def infer_missing_data(df):
    warnings = []

    # Infer depth
    if 'depth' not in df.columns:
        df['depth'] = df['url'].apply(lambda x: x.count('/'))
        warnings.append("Depth inferred from URL structure")

    # Infer navigation (assume top-level pages are in nav)
    if 'in_nav' not in df.columns:
        df['in_nav'] = df['depth'].apply(lambda x: True if x <= 2 else False)
        warnings.append("Navigation inferred from URL depth")

    # Infer linked_from (basic assumption: parent path)
    if 'linked_from' not in df.columns:
        df['linked_from'] = df['url'].apply(
            lambda x: '/'.join(x.split('/')[:-1]) if '/' in x else None
        )
        warnings.append("Link relationships inferred from URL hierarchy")

    return df, warnings

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
    metrics['Duplicate Pages %'] = round(
        (1 - metrics['Unique URLs'] / metrics['Total Pages']) * 100, 2
    )

    df['section'] = df['url'].apply(classify_section)
    section_dist = (df['section'].value_counts(normalize=True) * 100).round(2)

    # Navigation
    metrics['% Pages in Navigation'] = round(
        df['in_nav'].astype(int).mean() * 100, 2
    )

    # Orphans
    all_pages = set(df['url'])
    linked_pages = set(df['linked_from'].dropna())
    orphan_pages = all_pages - linked_pages
    metrics['% Orphan Pages'] = round(
        (len(orphan_pages) / len(all_pages)) * 100, 2
    )

    # Depth
    metrics['Avg Depth'] = round(df['depth'].mean(), 2)

    return metrics, section_dist

# -----------------------------
# Severity
# -----------------------------
def get_severity(metric, value):
    if not isinstance(value, (int, float)):
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
def generate_excel(df, metrics, section_dist):
    output = BytesIO()

    dashboard = []
    for k, v in metrics.items():
        dashboard.append([k, v, get_severity(k, v)])

    dashboard_df = pd.DataFrame(
        dashboard, columns=["Metric", "Value", "Severity"]
    )

    section_df = pd.DataFrame({
        "Section": section_dist.index,
        "Percentage": section_dist.values
    })

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dashboard_df.to_excel(writer, 'Dashboard', index=False)
        section_df.to_excel(writer, 'Sections', index=False)
        df.to_excel(writer, 'Raw Data', index=False)

    output.seek(0)

    wb = load_workbook(output)
    ws = wb['Dashboard']

    # Color coding
    colors = {
        "High": PatternFill(start_color="FFC7CE", fill_type="solid"),
        "Medium": PatternFill(start_color="FFEB9C", fill_type="solid"),
        "Low": PatternFill(start_color="C6EFCE", fill_type="solid"),
    }

    for row in ws.iter_rows(min_row=2, min_col=3):
        for cell in row:
            if cell.value in colors:
                cell.fill = colors[cell.value]

    # Pie chart
    ws2 = wb['Sections']
    pie = PieChart()

    data = Reference(ws2, min_col=2, min_row=1, max_row=len(section_df)+1)
    labels = Reference(ws2, min_col=1, min_row=2, max_row=len(section_df)+1)

    pie.add_data(data, titles_from_data=True)
    pie.set_categories(labels)
    pie.title = "Section Distribution"

    ws2.add_chart(pie, "E2")

    final = BytesIO()
    wb.save(final)
    final.seek(0)

    return final

# -----------------------------
# UI
# -----------------------------
st.title("📊 IA Audit Tool (Smart Inference Version)")

file = st.file_uploader("Upload CSV", type=['csv'])

if file:
    df = pd.read_csv(file)

    df = auto_map_columns(df)
    df['url'] = df['url'].apply(normalize_url)

    df, warnings = infer_missing_data(df)

    if warnings:
        st.warning(" | ".join(warnings))

    metrics, section_dist = calculate_metrics(df)

    tab1, tab2 = st.tabs(["Data", "Download"])

    with tab1:
        st.dataframe(df)

    with tab2:
        excel_file = generate_excel(df, metrics, section_dist)

        st.download_button(
            "Download Visual Excel Dashboard",
            data=excel_file,
            file_name="IA_Dashboard.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("Upload CSV to start analysis")