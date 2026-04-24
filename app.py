import streamlit as st
import pandas as pd

st.title("IA Audit Portal")

# Upload file
uploaded_file = st.file_uploader("Upload your URL file (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file:
    # Read file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Ensure column name
    df.columns = ["URL"]

    st.subheader("Raw Data")
    st.write(df.head())

    # -------- PROCESSING -------- #

    # Normalize URL
    def normalize(url):
        url = url.lower()
        url = url.replace('/en/', '/').replace('/ar/', '/')
        url = url.replace('.html', '')
        return url

    df["Normalized"] = df["URL"].apply(normalize)

    # Depth
    df["Depth"] = df["URL"].apply(lambda x: x.count("/") - 2)

    # Page Type
    def page_type(url):
        if "services" in url:
            return "Service"
        elif "doctor" in url:
            return "Doctor"
        elif "about" in url:
            return "About"
        elif "search" in url or "thank-you" in url:
            return "System"
        else:
            return "Other"

    df["PageType"] = df["URL"].apply(page_type)

    # Duplicate Key
    df["DuplicateKey"] = df["Normalized"].apply(lambda x: x.split("/", 2)[-1])

    df["DupCount"] = df.groupby("DuplicateKey")["DuplicateKey"].transform("count")

    # -------- METRICS -------- #

    total_pages = len(df)
    duplicate_pages = len(df[df["DupCount"] > 1])
    duplicate_percent = round((duplicate_pages / total_pages) * 100, 2)
    avg_depth = round(df["Depth"].mean(), 2)

    # Entry points
    doctor_entries = df[df["URL"].str.contains("find-a-doctor", case=False)].shape[0]
    service_entries = df[df["URL"].str.contains("services", case=False)].shape[0]

    # -------- DASHBOARD -------- #

    st.subheader("📊 IA Metrics")

    col1, col2 = st.columns(2)

    col1.metric("Total Pages", total_pages)
    col2.metric("Duplicate %", f"{duplicate_percent}%")

    col1.metric("Avg Depth", avg_depth)
    col2.metric("Doctor Entry Points", doctor_entries)

    st.metric("Service Entry Points", service_entries)

    # -------- CHARTS -------- #

    st.subheader("Page Type Distribution")
    st.bar_chart(df["PageType"].value_counts())

    st.subheader("Depth Distribution")
    st.bar_chart(df["Depth"].value_counts())

    # -------- DOWNLOAD -------- #

    st.subheader("Download Processed Data")

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "processed_data.csv", "text/csv")