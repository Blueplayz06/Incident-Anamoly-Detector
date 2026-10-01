"""
Incident Anomaly Dashboard (Streamlit) - reads REAL data from BigQuery only.

Tables: incident_logs.app_logs (raw request logs) and incident_logs.incidents
(rows written by the anomaly-detector function). There is no demo/mock mode.
"""

import os
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery

PROJECT_ID = os.environ.get("PROJECT_ID", "jio-cloud-training")
DATASET_ID = "incident_logs"
LOGS = f"`{PROJECT_ID}.{DATASET_ID}.app_logs`"
INCIDENTS = f"`{PROJECT_ID}.{DATASET_ID}.incidents`"
STALE_AFTER_SECONDS = 300

st.set_page_config(page_title="Incident Anomaly Dashboard", page_icon="🚨", layout="wide")

with st.sidebar:
    st.header("Settings")
    hours = st.select_slider("Time window (hours)", options=[1, 3, 6, 12, 24], value=3)
    auto_refresh = st.checkbox("Auto-refresh", value=False)
    refresh_seconds = st.slider("Refresh interval (seconds)", 10, 120, 30)
    if st.button("Refresh now"):
        st.cache_data.clear()


@st.cache_resource
def get_client():
    return bigquery.Client(project=PROJECT_ID)


def run_query(sql, hours=None):
    if hours is None:
        return get_client().query(sql).to_dataframe()
    cfg = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("hours", "INT64", hours)]
    )
    return get_client().query(sql, job_config=cfg).to_dataframe()


@st.cache_data(ttl=30, show_spinner=False)
def load_data(hours):
    in_window = "timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)"
    minutes = run_query(
        f"""
        SELECT TIMESTAMP_TRUNC(timestamp, MINUTE) AS bucket,
               COUNT(*) AS requests,
               COUNTIF(log_level = 'ERROR') AS errors,
               AVG(latency_ms) AS avg_latency
        FROM {LOGS}
        WHERE {in_window}
          AND timestamp < TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MINUTE)
        GROUP BY bucket
        ORDER BY bucket
        """,
        hours,
    )
    status = run_query(
        f"""
        SELECT CAST(status_code AS STRING) AS status_code, COUNT(*) AS n
        FROM {LOGS}
        WHERE {in_window}
        GROUP BY status_code
        ORDER BY status_code
        """,
        hours,
    )
    services = run_query(
        f"""
        SELECT service_name, COUNT(*) AS requests,
               COUNTIF(log_level = 'ERROR') AS errors
        FROM {LOGS}
        WHERE {in_window}
        GROUP BY service_name
        ORDER BY requests DESC
        """,
        hours,
    )
    incidents = run_query(
        f"""
        SELECT detected_at, anomaly_type, service_name, z_score,
               current_value, baseline_value, summary
        FROM {INCIDENTS}
        WHERE detected_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
        ORDER BY detected_at DESC
        LIMIT 50
        """,
        hours,
    )
    last_log = run_query(f"SELECT MAX(timestamp) AS last_log FROM {LOGS}")["last_log"].iloc[0]
    return minutes, status, services, incidents, last_log


try:
    minutes, status, services, incidents, last_log = load_data(hours)
except Exception as exc:  # show the real error instead of hiding it
    st.error(f"BigQuery query failed: {exc}")
    st.stop()

# ---- type cleanup -----------------------------------------------------------
if not minutes.empty:
    minutes["bucket"] = pd.to_datetime(minutes["bucket"], utc=True)
    for col in ("requests", "errors", "avg_latency"):
        minutes[col] = pd.to_numeric(minutes[col])
    minutes["error_rate"] = minutes["errors"] / minutes["requests"] * 100
if not incidents.empty:
    incidents["detected_at"] = pd.to_datetime(incidents["detected_at"], utc=True)
if not services.empty:
    services["error_rate"] = services["errors"] / services["requests"] * 100

# ---- header + freshness -----------------------------------------------------
st.title("🚨 Live Anomaly Detector")
now = pd.Timestamp.now(tz="UTC")
if pd.isna(last_log):
    st.warning("app_logs has no rows yet.")
    age_text = "no logs"
else:
    age = (now - pd.to_datetime(last_log, utc=True)).total_seconds()
    age_text = f"{int(age)}s ago"
    if age > STALE_AFTER_SECONDS:
        st.warning(
            f"No new logs for {int(age // 60)} min - the traffic generator may be stopped, "
            "so the charts below are not live."
        )
st.caption(
    f"Source: BigQuery `{PROJECT_ID}.{DATASET_ID}` | window: {hours}h | "
    f"last log: {age_text} | rendered {now.strftime('%H:%M:%S')} UTC"
)

# ---- KPI cards (latest complete minute) -------------------------------------
c1, c2, c3, c4 = st.columns(4)
if not minutes.empty:
    cur = minutes.iloc[-1]
    prev = minutes.iloc[-2] if len(minutes) > 1 else cur
    label = cur["bucket"].strftime("%H:%M")
    c1.metric(f"Requests ({label} UTC)", f"{int(cur['requests'])}", f"{int(cur['requests'] - prev['requests'])}")
    c2.metric("Error rate", f"{cur['error_rate']:.2f}%", f"{cur['error_rate'] - prev['error_rate']:.2f}%", delta_color="inverse")
    c3.metric("Avg latency", f"{cur['avg_latency']:.0f} ms", f"{cur['avg_latency'] - prev['avg_latency']:.0f} ms", delta_color="inverse")
else:
    c1.metric("Requests", "-")
    c2.metric("Error rate", "-")
    c3.metric("Avg latency", "-")
c4.metric(f"Incidents ({hours}h)", str(len(incidents)))

if minutes.empty:
    st.info("No complete minutes of logs in this window.")


def incident_markers(fig, anomaly_type, scale=1.0):
    """Overlay detector incidents on a chart so spike -> detection is visible."""
    if incidents.empty:
        return fig
    sub = incidents[incidents["anomaly_type"] == anomaly_type]
    if sub.empty:
        return fig
    fig.add_trace(
        go.Scatter(
            x=sub["detected_at"],
            y=pd.to_numeric(sub["current_value"]) * scale,
            mode="markers",
            marker=dict(symbol="x", size=12, color="red"),
            name="Incident detected",
        )
    )
    return fig


def style(fig):
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h"))
    return fig


# ---- charts -----------------------------------------------------------------
if not minutes.empty:
    left, right = st.columns(2)
    with left:
        st.subheader("Traffic volume (requests / min)")
        st.plotly_chart(style(px.area(minutes, x="bucket", y="requests")))
    with right:
        st.subheader("Error rate (%)")
        st.plotly_chart(style(incident_markers(px.area(minutes, x="bucket", y="error_rate"), "error_rate", 100)))

    left, right = st.columns(2)
    with left:
        st.subheader("Average latency (ms)")
        st.plotly_chart(style(incident_markers(px.area(minutes, x="bucket", y="avg_latency"), "latency")))
    with right:
        st.subheader("Status codes")
        if not status.empty:
            st.plotly_chart(style(px.bar(status, x="status_code", y="n").update_xaxes(type="category")))

    st.subheader("Services")
    if not services.empty:
        st.dataframe(services.round({"error_rate": 2}), hide_index=True)

# ---- incident log -----------------------------------------------------------
st.subheader("Recent incidents")
if incidents.empty:
    st.success(f"No incidents detected in the last {hours}h.")
else:
    show = incidents.copy()
    show["detected_at"] = show["detected_at"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    show["z_score"] = pd.to_numeric(show["z_score"]).round(1)
    for col in ("current_value", "baseline_value"):
        show[col] = pd.to_numeric(show[col]).round(3)
    st.dataframe(show, hide_index=True)

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()