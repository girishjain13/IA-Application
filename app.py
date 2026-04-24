def generate_excel(df, metrics, section_dist):
    from openpyxl import load_workbook
    from openpyxl.styles import PatternFill
    from openpyxl.chart import PieChart, Reference
    from io import BytesIO

    # -----------------------------
    # STEP 1: Write Excel (Buffer 1)
    # -----------------------------
    buffer1 = BytesIO()

    dashboard_rows = []
    for k, v in metrics.items():
        val = v if isinstance(v, (int, float)) else "N/A"

        severity = "N/A"
        if isinstance(v, (int, float)):
            if "Duplicate" in k:
                severity = "High" if v > 50 else "Medium" if v > 20 else "Low"
            elif "Orphan" in k:
                severity = "High" if v > 30 else "Medium" if v > 10 else "Low"
            elif "Depth" in k:
                severity = "High" if v > 4 else "Medium" if v > 3 else "Low"
            elif "Navigation" in k:
                severity = "High" if v < 50 else "Medium" if v < 70 else "Low"

        dashboard_rows.append({
            "Metric": str(k),
            "Value": val,
            "Severity": severity
        })

    dashboard_df = pd.DataFrame(dashboard_rows)

    section_df = pd.DataFrame({
        "Section": section_dist.index.astype(str),
        "Percentage": section_dist.values
    })

    with pd.ExcelWriter(buffer1, engine='openpyxl') as writer:
        dashboard_df.to_excel(writer, sheet_name='Dashboard', index=False)
        section_df.to_excel(writer, sheet_name='Sections', index=False)
        df.to_excel(writer, sheet_name='Raw Data', index=False)

    buffer1.seek(0)

    # -----------------------------
    # STEP 2: Load + Style (Buffer 2)
    # -----------------------------
    wb = load_workbook(buffer1)

    ws = wb['Dashboard']

    red = PatternFill(start_color="FFC7CE", fill_type="solid")
    yellow = PatternFill(start_color="FFEB9C", fill_type="solid")
    green = PatternFill(start_color="C6EFCE", fill_type="solid")

    for row in ws.iter_rows(min_row=2, min_col=3):
        for cell in row:
            if cell.value == "High":
                cell.fill = red
            elif cell.value == "Medium":
                cell.fill = yellow
            elif cell.value == "Low":
                cell.fill = green

    # -----------------------------
    # STEP 3: Add Chart
    # -----------------------------
    ws2 = wb['Sections']

    pie = PieChart()

    data = Reference(ws2, min_col=2, min_row=1, max_row=len(section_df)+1)
    labels = Reference(ws2, min_col=1, min_row=2, max_row=len(section_df)+1)

    pie.add_data(data, titles_from_data=True)
    pie.set_categories(labels)
    pie.title = "Section Distribution"

    ws2.add_chart(pie, "E2")

    # -----------------------------
    # STEP 4: Save to NEW buffer
    # -----------------------------
    buffer2 = BytesIO()
    wb.save(buffer2)
    buffer2.seek(0)

    return buffer2