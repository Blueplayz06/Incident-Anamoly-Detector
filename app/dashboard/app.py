import streamlit as st
import pandas as pd
from google.cloud import bigquery
import plotly.express as px
import os

# Set up page config
st.set_page_config(
    page_title="Incident Anomaly Dashboard",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Use blue and teal colors as requested
COLORS = {
    "blue": "#1f77b4", # infra metrics
    "teal": "#008080", # detection/incident metrics
    "error": "#d62728",
    "success": "#2ca02c"
}

# --- Data Fetching ---

# Default to searching for 'incident_logs' dataset, project can be inferred from default creds or env var
PROJECT_ID = os.environ.get("PROJECT_ID") 
DATASET_ID = "incident_logs"

# Sidebar toggle for demo mode
with st.sidebar:
    st.header("Settings")
    use_demo_data = st.checkbox("Use Demo Data (No GCP required)", value=True, help="Toggle this to view the dashboard with mock data instead of connecting to BigQuery.")

@st.cache_data(ttl=60) # Cache data for 60 seconds
def fetch_data(use_demo=False):
    if use_demo:
        return generate_mock_data()
        
    client = bigquery.Client(project=PROJECT_ID)
    
    # Get last updated timestamp
    last_updated_query = f"""
        SELECT MAX(timestamp) as last_update 
        FROM `{DATASET_ID}.app_logs`
    """
    try:
        last_updated_df = client.query(last_updated_query).to_dataframe()
        last_update = last_updated_df['last_update'].iloc[0] if not last_updated_df.empty else None
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return None, None, None, None, None, None

    # Time window for queries: last 24 hours
    
    # 1. Traffic overview (Requests per minute)
    traffic_query = f"""
        SELECT 
            TIMESTAMP_TRUNC(timestamp, MINUTE) as minute,
            COUNT(*) as request_count,
            COUNTIF(status_code >= 500) as error_count
        FROM `{DATASET_ID}.app_logs`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        GROUP BY 1
        ORDER BY 1
    """
    traffic_df = client.query(traffic_query).to_dataframe()
    
    # Calculate error rate in traffic df
    if not traffic_df.empty:
        traffic_df['error_rate'] = (traffic_df['error_count'] / traffic_df['request_count']) * 100
    
    # 2. Performance (Average latency over time)
    latency_query = f"""
        SELECT 
            TIMESTAMP_TRUNC(timestamp, MINUTE) as minute,
            AVG(latency_ms) as avg_latency
        FROM `{DATASET_ID}.app_logs`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        GROUP BY 1
        ORDER BY 1
    """
    latency_df = client.query(latency_query).to_dataframe()
    
    # 3. Status code breakdown
    status_query = f"""
        SELECT 
            CAST(status_code AS STRING) as status_code,
            COUNT(*) as count
        FROM `{DATASET_ID}.app_logs`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        GROUP BY 1
        ORDER BY 1
    """
    status_df = client.query(status_query).to_dataframe()
    
    # 4. Service Breakdown
    service_query = f"""
        SELECT 
            service_name,
            COUNT(*) as request_count,
            COUNTIF(status_code >= 500) as error_count
        FROM `{DATASET_ID}.app_logs`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        GROUP BY 1
        ORDER BY 2 DESC
    """
    service_df = client.query(service_query).to_dataframe()
    if not service_df.empty:
        service_df['error_rate'] = (service_df['error_count'] / service_df['request_count']) * 100

    # 5. Recent Incidents
    incidents_query = f"""
        SELECT 
            detected_at,
            anomaly_type,
            service_name,
            z_score,
            summary
        FROM `{DATASET_ID}.incidents`
        ORDER BY detected_at DESC
        LIMIT 20
    """
    incidents_df = client.query(incidents_query).to_dataframe()
    
    return last_update, traffic_df, latency_df, status_df, service_df, incidents_df

def generate_mock_data():
    """Generates fake data for UI testing without GCP credentials."""
    import numpy as np
    
    now = pd.Timestamp.utcnow()
    last_update = now
    
    # Generate 60 minutes of data
    minutes = [now - pd.Timedelta(minutes=i) for i in range(60, 0, -1)]
    
    # Traffic
    base_requests = np.random.normal(500, 50, 60)
    base_requests[45:50] += 800  # simulate spike
    error_counts = base_requests * np.random.uniform(0.01, 0.05, 60)
    error_counts[45:50] = base_requests[45:50] * 0.4  # simulate error spike
    
    traffic_df = pd.DataFrame({
        'minute': minutes,
        'request_count': base_requests,
        'error_count': error_counts
    })
    traffic_df['error_rate'] = (traffic_df['error_count'] / traffic_df['request_count']) * 100
    
    # Latency
    base_latency = np.random.normal(120, 15, 60)
    base_latency[45:50] += 400 # simulate latency spike
    latency_df = pd.DataFrame({
        'minute': minutes,
        'avg_latency': base_latency
    })
    
    # Status codes
    status_df = pd.DataFrame({
        'status_code': ['200', '400', '404', '500', '503'],
        'count': [25000, 500, 150, 800, 200]
    })
    
    # Service breakdown
    service_df = pd.DataFrame({
        'service_name': ['frontend', 'auth-api', 'cart-service', 'payment-gateway', 'inventory-db'],
        'request_count': [15000, 5000, 3000, 2000, 1650],
        'error_rate': [0.5, 1.2, 5.0, 15.5, 0.1]
    })
    
    # Incidents
    incidents_df = pd.DataFrame({
        'detected_at': [now - pd.Timedelta(minutes=10), now - pd.Timedelta(hours=2), now - pd.Timedelta(days=1)],
        'anomaly_type': ['error_rate', 'latency', 'error_rate'],
        'service_name': ['payment-gateway', 'cart-service', 'auth-api'],
        'z_score': [8.5, 4.2, 5.1],
        'summary': [
            "Payment-gateway error rate spiked 1500% above baseline. Likely related to recent deployment.",
            "Cart-service average latency reached 550ms (z=4.2).",
            "Auth-api seeing elevated 500 errors. 120 errors in the last 5 minutes."
        ]
    })
    
    return last_update, traffic_df, latency_df, status_df, service_df, incidents_df

# --- Layout ---

st.title("🚨 Incident/Log Anomaly Dashboard")

# Manual refresh
col1, col2 = st.columns([8, 1])
with col2:
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()

# Fetch data
with st.spinner(f"Fetching {'demo' if use_demo_data else 'BigQuery'} data..."):
    last_update, traffic_df, latency_df, status_df, service_df, incidents_df = fetch_data(use_demo=use_demo_data)

if last_update is None:
    st.warning("No data found or BigQuery connection not established yet.")
    st.stop()

# 1. Header / status strip
time_diff = pd.Timestamp.utcnow().tz_localize(None) - last_update.tz_localize(None)
minutes_ago = int(time_diff.total_seconds() / 60)
st.markdown(f"**Status:** Live | **Last data received:** {minutes_ago} minutes ago ({last_update.strftime('%Y-%m-%d %H:%M:%S')} UTC)")
st.markdown("---")

# 2. Traffic overview row
st.subheader("Traffic Overview")
col_traffic1, col_traffic2 = st.columns(2)

with col_traffic1:
    if not traffic_df.empty:
        fig_traffic = px.line(traffic_df, x='minute', y='request_count', 
                              color_discrete_sequence=[COLORS["blue"]])
        fig_traffic.update_layout(margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_traffic, use_container_width=True)
        st.caption("Request volume over time (requests per minute)")
    else:
        st.info("No traffic data in the last 24 hours.")

with col_traffic2:
    if not traffic_df.empty:
        fig_error = px.line(traffic_df, x='minute', y='error_rate',
                            color_discrete_sequence=[COLORS["teal"]])
        fig_error.update_layout(margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_error, use_container_width=True)
        st.caption("Error rate over time (% of 5xx responses)")
    else:
        st.info("No error rate data in the last 24 hours.")

st.markdown("---")

# 3. Performance row
st.subheader("Performance & Health")
col_perf1, col_perf2 = st.columns(2)

with col_perf1:
    if not latency_df.empty:
        fig_lat = px.line(latency_df, x='minute', y='avg_latency',
                          color_discrete_sequence=[COLORS["blue"]])
        fig_lat.update_layout(margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_lat, use_container_width=True)
        st.caption("Average latency over time (ms)")
    else:
        st.info("No latency data in the last 24 hours.")

with col_perf2:
    if not status_df.empty:
        fig_status = px.pie(status_df, values='count', names='status_code',
                            color_discrete_sequence=px.colors.sequential.Teal)
        fig_status.update_layout(margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_status, use_container_width=True)
        st.caption("Status code breakdown")
    else:
        st.info("No status code data in the last 24 hours.")

st.markdown("---")

# 4. Service breakdown
st.subheader("Service Breakdown")
if not service_df.empty:
    col_svc1, col_svc2 = st.columns(2)
    with col_svc1:
        fig_svc_req = px.bar(service_df, x='service_name', y='request_count',
                             color_discrete_sequence=[COLORS["blue"]])
        st.plotly_chart(fig_svc_req, use_container_width=True)
        st.caption("Total requests per service")
    with col_svc2:
        fig_svc_err = px.bar(service_df, x='service_name', y='error_rate',
                             color_discrete_sequence=[COLORS["teal"]])
        st.plotly_chart(fig_svc_err, use_container_width=True)
        st.caption("Error rate per service (%)")
else:
    st.info("No service breakdown data in the last 24 hours.")

st.markdown("---")

# 5. Recent incidents section
st.subheader("Recent Incidents")
if not incidents_df.empty:
    # Format the dataframe for display
    display_df = incidents_df.copy()
    display_df['detected_at'] = display_df['detected_at'].dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    display_df = display_df.rename(columns={
        'detected_at': 'Timestamp',
        'anomaly_type': 'Type',
        'service_name': 'Service',
        'z_score': 'Z-Score',
        'summary': 'Summary'
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.caption("Recent anomalies detected and their generated summaries, most recent first.")
else:
    st.success("No incidents detected! 🎉")
