import streamlit as st
import pandas as pd
from io import BytesIO
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
        original = df.columns[0]
        df.rename(columns={original: 'url'}, inplace=True)
        st.warning(f"No URL column found. Using '{original}' as URL.")

    return df

# -----------------------------
# Inference Engine
# -----------------------------
def infer_data(df):
    messages = []

    if 'depth' not in df.columns:
        df['depth'] = df['url'].apply(lambda x: x.count('/'))
        messages.append("Depth inferred")

    if 'in_nav' not in df.columns:
        df['in_nav'] = df['depth'].apply(lambda x: x <= 2)
        messages.append("Navigation inferred")

    if 'linked_from' not in df.columns:
        df['linked_from'] = df['url'].apply(
            lambda x: '/'.join(x.split('/')[:-1]) if '/' in x else None
        )
        messages.append("Link relationships inferred")

    return df, messages

# -----------------------------
# Metrics
# -----------------------------
def calculate_metrics(df):
    metrics = {}

    metrics['Total Pages'] = len(df)
    metrics['Unique URLs'] = df['url'].nunique()

    if metrics['Total Pages'] > 0:
        metrics['Duplicate Pages %'] = round(
            (1 - metrics['Unique URLs'] / metrics['Total Pages']) * 100, 2
        )
    else:
        metrics['Duplicate Pages %'] = 0

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
    ) if len(all_pages) > 0 else 0

    # Depth
    metrics['Avg Depth'] = round(df['depth'].mean(), 2)

    # Sections
    df['section'] = df['url'].apply(
        lambda x: "Doctors" if "doctor" in x else
        "Services" if "service" in x else
        "Locations" if "location" in x else
        "Content" if "blog" in x or "news" in x else
        "Other"
    )

    section_dist = (df['section'].value_counts(normalize=True) * 100).round(2)

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
# Excel Generator (SAFE)
# -----------------------------
def generate_excel(df, metrics, section_dist):

    # STEP 1: Write base file
    buffer1 = BytesIO()

    dashboard_data = []
    for k, v in metrics.items():
        dashboard_data.append({
            "Metric": k,
            "Value": v,
            "Severity": get_severity(k, v)
        })

    dashboard_df = pd.DataFrame(dashboard_data)

    section_df = pd.DataFrame({
        "Section": section_dist.index.astype(str),
        "Percentage": section_dist.values
    })

    with pd.ExcelWriter(buffer1, engine='openpyxl') as writer:
        dashboard_df.to_excel(writer, sheet_name='Dashboard', index=False)
        section_df.to_excel(writer, sheet_name='Sections', index=False)
        df.to_excel(writer, sheet_name='Raw Data', index=False)

    buffer1.seek(0)

    # STEP 2: Load workbook
    wb = load_workbook(buffer1)

    # Safe styling
    if 'Dashboard' in wb.sheetnames:
        ws = wb['Dashboard']

        colors = {
            "High": PatternFill(start_color="FFC7CE", fill_type="solid"),
            "Medium": PatternFill(start_color="FFEB9C", fill_type="solid"),
            "Low": PatternFill(start_color="C6EFCE", fill_type="solid"),
        }

        for row in ws.iter_rows(min_row=2, min_col=3):
            for cell in row:
                if cell.value in colors:
                    cell.fill = colors[cell.value]

    # Safe chart
    if 'Sections' in wb.sheetnames and len(section_df) > 0:
        ws2 = wb['Sections']

        try:
            pie = PieChart()

            data = Reference(ws2, min_col=2, min_row=1, max_row=len(section_df)+1)
            labels = Reference(ws2, min_col=1, min_row=2, max_row=len(section_df)+1)

            pie.add_data(data, titles_from_data=True)
            pie.set_categories(labels)
            pie.title = "Section Distribution"

            ws2.add_chart(pie, "E2")
        except:
            pass  # prevent crash

    # STEP 3: Save final
    buffer2 = BytesIO()
    wb.save(buffer2)
    buffer2.seek(0)

    return buffer2

# -----------------------------
# UI
# -----------------------------
st.title("📊 IA Audit Tool (Crash-Proof Version)")

file = st.file_uploader("Upload CSV", type=['csv'])

if file:
    try:
        df = pd.read_csv(file)

        df = auto_map_columns(df)
        df['url'] = df['url'].apply(normalize_url)

        df, msgs = infer_data(df)

        if msgs:
            st.warning(" | ".join(msgs))

        metrics, section_dist = calculate_metrics(df)

        tab1, tab2 = st.tabs(["Data", "Download"])

        with tab1:
            st.dataframe(df)

        with tab2:
            try:
                excel_file = generate_excel(df, metrics, section_dist)

                st.download_button(
                    "Download Visual Excel Dashboard",
                    data=excel_file,
                    file_name="IA_Dashboard.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Excel generation failed: {str(e)}")

    except Exception as e:
        st.error(f"App error: {str(e)}")

else:
    st.info("Upload CSV to start analysis")