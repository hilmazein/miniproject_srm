from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import plotly.graph_objects as go
import json
from plotly.utils import PlotlyJSONEncoder
from datetime import datetime, timedelta

app = Flask(__name__)

# MongoDB Configuration
client = MongoClient("mongodb://localhost:27017/")
db = client["risk_management"]
assessments_collection = db["assessments"]

# Fungsi untuk menentukan risk level berdasarkan data yang diisi user
def determine_risk_level(user_data):
    if 'critical' in user_data.lower() or 'high' in user_data.lower():
        return 'High'
    elif 'moderate' in user_data.lower() or 'medium' in user_data.lower():
        return 'Medium'
    else:
        return 'Low'

# Fungsi untuk menentukan recommended controls berdasarkan risk level
def determine_recommended_controls(risk_level):
    controls = {
        'High': 'Implement strong encryption, multi-factor authentication, and continuous monitoring.',
        'Medium': 'Ensure access controls, perform regular audits, and implement network segmentation.',
        'Low': 'Keep software updated, apply basic security policies, and perform periodic reviews.'
    }
    return controls.get(risk_level, 'Standard security measures.')

# Dashboard Route
@app.route("/")
def dashboard():
    # Mengambil data untuk Risk Assessment Overview dari MongoDB
    assessments_data = list(assessments_collection.find({}, {"_id": 0}))

    # Menentukan waktu 6 bulan terakhir
    months = [datetime.now() - timedelta(days=i*30) for i in range(6)]
    months = [month.strftime("%b %Y") for month in months]

    # Menginisialisasi jumlah untuk setiap kategori
    total_risks = {month: 0 for month in months}
    critical_risks = {month: 0 for month in months}
    mitigated_risks = {month: 0 for month in months}
    active_threats = {month: 0 for month in months}

    # Menghitung jumlah untuk setiap kategori berdasarkan data dari assessments
    for assessment in assessments_data:
        try:
            # Menggunakan strptime untuk parsing string menjadi datetime
            assessment_date = datetime.strptime(assessment["date"], "%Y-%m-%d %H:%M:%S")
            month = assessment_date.strftime("%b %Y")
        except Exception as e:
            print(f"Error parsing date: {assessment['date']}, Error: {e}")
            continue
        
        if month in months:
            total_risks[month] += 1
            if assessment["risk_level"] == "High":
                critical_risks[month] += 1
            if assessment.get("recommended_controls"):
                mitigated_risks[month] += 1
            active_threats[month] += 1  # Asumsi: setiap assessment mewakili ancaman

    # Menyiapkan data untuk Plotly chart
    bar_chart = go.Figure()

    bar_chart.add_trace(go.Bar(
        x=months,
        y=[total_risks[month] for month in months],
        name="Total Risks",
        marker_color="blue",
        text=[total_risks[month] for month in months],
        textposition='none'
    ))

    bar_chart.add_trace(go.Bar(
        x=months,
        y=[critical_risks[month] for month in months],
        name="Critical Risks",
        marker_color="red",
        text=[critical_risks[month] for month in months],
        textposition='none'
    ))

    bar_chart.add_trace(go.Bar(
        x=months,
        y=[mitigated_risks[month] for month in months],
        name="Mitigated Risks",
        marker_color="green",
        text=[mitigated_risks[month] for month in months],
        textposition='none'
    ))

    bar_chart.add_trace(go.Bar(
        x=months,
        y=[active_threats[month] for month in months],
        name="Active Threats",
        marker_color="yellow",
        text=[active_threats[month] for month in months],
        textposition='none'
    ))

    bar_chart.update_layout(
        barmode='group',
        title="Risk Assessment Overview (Last 6 Months)",
        xaxis_title="Month",
        yaxis_title="Count",
        showlegend=True,
        autosize=True,
        height=600,  # Atur tinggi grafik
        width=1200,   # Atur lebar grafik
    )

    bar_chart_json = json.dumps(bar_chart, cls=PlotlyJSONEncoder)

    # Grafik Threat Trends - Mengambil Data dari MongoDB
    threats_data = list(db["threats"].find({}, {"_id": 0}))
    line_chart = go.Figure(
        data=[go.Scatter(
            x=[threat["month"] for threat in threats_data],
            y=[threat["threats"] for threat in threats_data],
            mode="lines+markers",
            line=dict(color="indigo"),
        )]
    )
    line_chart.update_layout(
        title="Threat Trends",
        xaxis_title="Month",
        yaxis_title="Threats",
        height=600,  # Atur tinggi grafik
        width=1200,   # Atur lebar grafik
    )
    line_chart_json = json.dumps(line_chart, cls=PlotlyJSONEncoder)

    return render_template(
        "dashboard.html",
        total_risks=total_risks,
        critical_risks=critical_risks,
        mitigated_risks=mitigated_risks,
        active_threats=active_threats,
        bar_chart_json=bar_chart_json,
        line_chart_json=line_chart_json,
    )

# Assessment Page
@app.route("/assessments")
def assessments():
    return render_template("assessments.html")

# Save Assessment (with Auto Risk Level & Recommended Controls)
@app.route("/save-assessment", methods=["POST"])
def save_assessment():
    data = request.json

    # Menggabungkan semua jawaban user untuk dianalisis
    combined_data = " ".join(data.values())

    # Menentukan Risk Level & Recommended Controls
    risk_level = determine_risk_level(combined_data)
    recommended_controls = determine_recommended_controls(risk_level)

    # Tambahkan tanggal assessment
    data.update({
        "risk_level": risk_level,
        "recommended_controls": recommended_controls,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    # Simpan ke MongoDB
    assessments_collection.insert_one(data)

    return jsonify({"message": "Assessment saved successfully!", "risk_level": risk_level, "recommended_controls": recommended_controls})
    
# Reports Page
@app.route("/reports", methods=["GET", "POST"])
def reports():
    reports_data = list(assessments_collection.find({}, {"_id": 0}))
    project_names = list(set(report["project_name"] for report in reports_data))

    # Jika ada proyek yang dipilih, tampilkan grafik berdasarkan proyek tersebut
    selected_project = request.form.get("project_name")
    if selected_project:
        project_data = [report for report in reports_data if report["project_name"] == selected_project]
        # Grafik untuk proyek yang dipilih
        total_risks = len(project_data)
        critical_risks = sum(1 for a in project_data if a.get("risk_level") == "High")
        mitigated_risks = sum(1 for a in project_data if a.get("recommended_controls"))
        active_threats = total_risks - mitigated_risks

        # Menyiapkan data untuk grafik per proyek
        bar_chart = go.Figure()

        bar_chart.add_trace(go.Bar(
            x=[selected_project],
            y=[total_risks],
            name="Total Risks",
            marker_color="blue",
        ))

        bar_chart.add_trace(go.Bar(
            x=[selected_project],
            y=[critical_risks],
            name="Critical Risks",
            marker_color="red",
        ))

        bar_chart.add_trace(go.Bar(
            x=[selected_project],
            y=[mitigated_risks],
            name="Mitigated Risks",
            marker_color="green",
        ))

        bar_chart.add_trace(go.Bar(
            x=[selected_project],
            y=[active_threats],
            name="Active Threats",
            marker_color="yellow",
        ))

        bar_chart.update_layout(
            barmode='group',
            title=f"Risk Assessment Overview for {selected_project}",
            xaxis_title="Project",
            yaxis_title="Count",
            showlegend=True
        )

        bar_chart_json = json.dumps(bar_chart, cls=PlotlyJSONEncoder)
        return render_template("reports.html", reports=reports_data, project_names=project_names, selected_project=selected_project, bar_chart_json=bar_chart_json)

    return render_template("reports.html", reports=reports_data, project_names=project_names)

# API untuk mengambil Risk Chart berdasarkan proyek
@app.route("/get-risk-chart", methods=["POST"])
def get_risk_chart():
    data = request.json
    project_name = data.get("project_name")

    assessments = list(assessments_collection.find({"project_name": project_name}, {"_id": 0}))

    risk_counts = {"High": 0, "Medium": 0, "Low": 0}
    for assessment in assessments:
        risk_counts[assessment["risk_level"]] += 1

    risk_chart = go.Figure(data=[
        go.Bar(x=list(risk_counts.keys()), y=list(risk_counts.values()), marker_color=["red", "orange", "green"])
    ])
    risk_chart.update_layout(title=f"Risk Chart for {project_name}", xaxis_title="Risk Level", yaxis_title="Count")

    return jsonify({"risk_chart_json": json.dumps(risk_chart, cls=PlotlyJSONEncoder)})

# Profile Page
@app.route("/profile")
def profile():
    return render_template("profile.html")

# Run Flask App
if __name__ == "__main__":
    app.run(debug=True)
