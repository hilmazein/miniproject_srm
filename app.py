from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import plotly.graph_objects as go
import json
from plotly.utils import PlotlyJSONEncoder
from pymisp import PyMISP

app = Flask(__name__)

# MongoDB Configuration
client = MongoClient("mongodb://localhost:27017/")
db = client["risk_management"]  
risks_collection = db["risks"]
threats_collection = db["threats"]
assessments_collection = db["assessments"]  

@app.route("/")
def dashboard():
    risks_data = list(risks_collection.find({}, {"_id": 0}))
    threats_data = list(threats_collection.find({}, {"_id": 0}))
    assessments_data = list(assessments_collection.find({}, {"_id": 0}))  

    bar_chart = go.Figure(
        data=[
            go.Bar(
                x=[risk["name"] for risk in risks_data],
                y=[risk["value"] for risk in risks_data],
                marker_color="indigo",
            )
        ]
    )
    bar_chart.update_layout(title="Risk Distribution", xaxis_title="Risk Level", yaxis_title="Count")

    line_chart = go.Figure(
        data=[
            go.Scatter(
                x=[threat["month"] for threat in threats_data],
                y=[threat["threats"] for threat in threats_data],
                mode="lines+markers",
                line=dict(color="indigo"),
            )
        ]
    )
    line_chart.update_layout(title="Threat Trends", xaxis_title="Month", yaxis_title="Threats")

    bar_chart_json = json.dumps(bar_chart, cls=PlotlyJSONEncoder)
    line_chart_json = json.dumps(line_chart, cls=PlotlyJSONEncoder)

    total_risks = len(assessments_data)
    critical_risks = sum(1 for a in assessments_data if a.get("risk_level") == "High")
    mitigated_risks = sum(1 for a in assessments_data if a.get("recommended_controls"))
    active_threats = total_risks - mitigated_risks

    return render_template(
        "dashboard.html",
        total_risks=total_risks,
        critical_risks=critical_risks,
        mitigated_risks=mitigated_risks,
        active_threats=active_threats,
        bar_chart_json=bar_chart_json,
        line_chart_json=line_chart_json,
    )

@app.route("/assessments")
def assessments():
    return render_template("assessments.html")

@app.route("/save-assessment", methods=["POST"])
def save_assessment():
    data = request.json
    assessments_collection.insert_one(data)  
    return jsonify({"message": "Assessment saved successfully!"})

@app.route("/misp-integration")
def misp_integration():
    return render_template("misp_integration.html")

@app.route("/fetch-misp-data", methods=["POST"])
def fetch_misp_data():
    data = request.json
    misp_url = data.get("misp_url")
    api_key = data.get("api_key")
    
    misp = PyMISP(misp_url, api_key, False)
    events = misp.search(controller="events", limit=5)
    
    threats = []
    categories = {}
    for event in events.get("response", []):
        threat = {
            "event_id": event["Event"]["id"],
            "threat_level": event["Event"]["threat_level_id"],
            "category": event["Event"]["info"],
            "date": event["Event"]["date"]
        }
        threats.append(threat)
        categories[event["Event"]["info"]] = categories.get(event["Event"]["info"], 0) + 1
    
    return jsonify({"threats": threats, "categories": list(categories.keys()), "counts": list(categories.values())})

@app.route("/reports")
def reports():
    return render_template("reports.html")

@app.route("/profile")
def profile():
    return render_template("profile.html")

if __name__ == "__main__":
    app.run(debug=True)
