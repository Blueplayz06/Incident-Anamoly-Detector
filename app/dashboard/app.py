import streamlit as st
import pandas as pd
from google.cloud import bigquery
import plotly.express as px
import plotly.graph_objects as go
import os
import time
import numpy as np

# Set up page config
st.set_page_config(
    page_title="Incident Anomaly Dashboard",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium colors
COLORS = {
    "primary": "#00f2fe",     # vibrant cyan
    "secondary": "#4facfe",   # bright blue
    "accent": "#ff0844",      # vibrant red for errors
    "background": "#0e1117",
    "card": "#1a1c23",
    "text": "#ffffff"
}

# --- Settings & State ---
PROJECT_ID = os.environ.get("PROJECT_ID") 
DATASET_ID = "incident_logs"

with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("---")
    use_demo_data = st.checkbox("🧪 Use Demo Data", value=True, help="Simulate a live data stream without GCP.")
    auto_refresh = st.checkbox("🔄 Live Auto-Refresh", value=True, help="Automatically refresh the dashboard to simulate real-time monitoring.")
    refresh_rate = st.slider("Refresh Interval (seconds)", min_value=1, max_value=10, value=2)

# --- Data Generation (Stateful Demo Mode) ---
def init_mock_state():
    if "mock_initialized" not in st.session_state:
        now = pd.Timestamp.utcnow()
        minutes = [now - pd.Timedelta(seconds=i*5) for i in range(60, 0, -1)] # 60 points, 5 seconds apart
        
        # Traffic
        base_reqs = np.random.normal(500, 50, 60)
        err_reqs = base_reqs * np.random.uniform(0.01, 0.05, 60)
        st.session_state.traffic_df = pd.DataFrame({
            'time': minutes, 'request_count': base_reqs, 'error_count': err_reqs
        })
        
        # Latency
        st.session_state.latency_df = pd.DataFrame({
            'time': minutes, 'avg_latency': np.random.normal(120, 15, 60)
        })
        
        # Status
        st.session_state.status_df = pd.DataFrame({
            'status_code': ['200', '400', '404', '500', '503'],
            'count': [25000, 500, 150, 800, 200]
        })
        
        # Services
        st.session_state.service_df = pd.DataFrame({
            'service_name': ['frontend', 'auth-api', 'cart-service', 'payment-gateway', 'inventory-db'],
            'request_count': [15000, 5000, 3000, 2000, 1650],
            'error_count': [75, 60, 150, 310, 1]
        })
        
        # Incidents
        st.session_state.incidents_df = pd.DataFrame({
            'detected_at': [now - pd.Timedelta(minutes=10), now - pd.Timedelta(hours=2)],
            'anomaly_type': ['error_rate', 'latency'],
            'service_name': ['payment-gateway', 'cart-service'],
            'z_score': [8.5, 4.2],
            'summary': [
                "Payment-gateway error rate spiked 1500% above baseline. Likely related to recent deployment.",
                "Cart-service average latency reached 550ms (z=4.2)."
            ]
        })
        st.session_state.mock_initialized = True

def advance_mock_state():
    now = pd.Timestamp.utcnow()
    
    # 10% chance of an anomaly spike
    is_anomaly = np.random.random() > 0.9
    
    req_count = np.random.normal(500, 50)
    err_count = req_count * (np.random.uniform(0.3, 0.5) if is_anomaly else np.random.uniform(0.01, 0.05))
    lat = np.random.normal(120, 15) + (300 if is_anomaly else 0)
    
    # Update Traffic
    new_traffic = pd.DataFrame({'time': [now], 'request_count': [req_count], 'error_count': [err_count]})
    st.session_state.traffic_df = pd.concat([st.session_state.traffic_df.iloc[1:], new_traffic], ignore_index=True)
    
    # Update Latency
    new_lat = pd.DataFrame({'time': [now], 'avg_latency': [lat]})
    st.session_state.latency_df = pd.concat([st.session_state.latency_df.iloc[1:], new_lat], ignore_index=True)
    
    # Update Status & Services randomly to simulate live data
    st.session_state.status_df['count'] += np.random.randint(10, 100, 5)
    st.session_state.service_df['request_count'] += np.random.randint(10, 100, 5)
    st.session_state.service_df['error_count'] += np.random.randint(0, 5, 5)
    
    # Occasionally generate an incident if anomaly occurs
    if is_anomaly and np.random.random() > 0.5:
        new_inc = pd.DataFrame({
            'detected_at': [now],
            'anomaly_type': ['spike'],
            'service_name': [np.random.choice(st.session_state.service_df['service_name'])],
            'z_score': [np.round(np.random.uniform(3.5, 9.0), 2)],
            'summary': [f"Sudden traffic/error spike detected dynamically."]
        })
        st.session_state.incidents_df = pd.concat([new_inc, st.session_state.incidents_df]).head(20)

@st.cache_data(ttl=60)
def fetch_real_data():
    client = bigquery.Client(project=PROJECT_ID)
    try:
        last_updated_df = client.query(f"SELECT MAX(timestamp) as last_update FROM `{DATASET_ID}.app_logs`").to_dataframe()
        last_update = last_updated_df['last_update'].iloc[0] if not last_updated_df.empty else None
    except Exception as e:
        return None, None, None, None, None, None

    traffic_df = client.query(f"SELECT TIMESTAMP_TRUNC(timestamp, MINUTE) as time, COUNT(*) as request_count, COUNTIF(status_code >= 500) as error_count FROM `{DATASET_ID}.app_logs` WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR) GROUP BY 1 ORDER BY 1").to_dataframe()
    latency_df = client.query(f"SELECT TIMESTAMP_TRUNC(timestamp, MINUTE) as time, AVG(latency_ms) as avg_latency FROM `{DATASET_ID}.app_logs` WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR) GROUP BY 1 ORDER BY 1").to_dataframe()
    status_df = client.query(f"SELECT CAST(status_code AS STRING) as status_code, COUNT(*) as count FROM `{DATASET_ID}.app_logs` WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR) GROUP BY 1 ORDER BY 1").to_dataframe()
    service_df = client.query(f"SELECT service_name, COUNT(*) as request_count, COUNTIF(status_code >= 500) as error_count FROM `{DATASET_ID}.app_logs` WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR) GROUP BY 1 ORDER BY 2 DESC").to_dataframe()
    incidents_df = client.query(f"SELECT detected_at, anomaly_type, service_name, z_score, summary FROM `{DATASET_ID}.incidents` ORDER BY detected_at DESC LIMIT 20").to_dataframe()
    
    return last_update, traffic_df, latency_df, status_df, service_df, incidents_df

# Fetch data logic
if use_demo_data:
    init_mock_state()
    if auto_refresh:
        advance_mock_state()
    traffic_df = st.session_state.traffic_df.copy()
    latency_df = st.session_state.latency_df.copy()
    status_df = st.session_state.status_df.copy()
    service_df = st.session_state.service_df.copy()
    incidents_df = st.session_state.incidents_df.copy()
    last_update = pd.Timestamp.utcnow()
    
    # Calculate error rate for dataframes
    traffic_df['error_rate'] = (traffic_df['error_count'] / traffic_df['request_count']) * 100
    service_df['error_rate'] = (service_df['error_count'] / service_df['request_count']) * 100
else:
    last_update, traffic_df, latency_df, status_df, service_df, incidents_df = fetch_real_data()
    if traffic_df is not None and not traffic_df.empty:
        traffic_df['error_rate'] = (traffic_df['error_count'] / traffic_df['request_count']) * 100
    if service_df is not None and not service_df.empty:
        service_df['error_rate'] = (service_df['error_count'] / service_df['request_count']) * 100

if last_update is None:
    st.error("No data found or BigQuery connection failed.")
    st.stop()

# --- Layout & Aesthetics ---

st.title("🚨 Live Anomaly Detector")
st.markdown(f"**Last Sync:** `{last_update.strftime('%Y-%m-%d %H:%M:%S')} UTC`  |  **Source:** `{'Mock Stream' if use_demo_data else 'GCP BigQuery'}`")
st.markdown("<br>", unsafe_allow_html=True)

# 1. KPI Cards
if not traffic_df.empty and not latency_df.empty:
    curr_req = traffic_df['request_count'].iloc[-1]
    prev_req = traffic_df['request_count'].iloc[-2] if len(traffic_df) > 1 else curr_req
    
    curr_err = traffic_df['error_rate'].iloc[-1]
    prev_err = traffic_df['error_rate'].iloc[-2] if len(traffic_df) > 1 else curr_err
    
    curr_lat = latency_df['avg_latency'].iloc[-1]
    prev_lat = latency_df['avg_latency'].iloc[-2] if len(latency_df) > 1 else curr_lat
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Requests (Current)", f"{int(curr_req)}", f"{int(curr_req - prev_req)}", delta_color="normal")
    col2.metric("Error Rate", f"{curr_err:.2f}%", f"{curr_err - prev_err:.2f}%", delta_color="inverse")
    col3.metric("Avg Latency", f"{curr_lat:.0f} ms", f"{curr_lat - prev_lat:.0f} ms", delta_color="inverse")
    col4.metric("Active Incidents", f"{len(incidents_df)}", f"0", delta_color="off")
    st.markdown("<br>", unsafe_allow_html=True)

# Common chart styling
def style_chart(fig):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', zeroline=False)
    )
    return fig

# 2. Traffic & Errors
col_t1, col_t2 = st.columns(2)
with col_t1:
    st.subheader("Traffic Volume")
    if not traffic_df.empty:
        fig_traffic = px.area(traffic_df, x='time', y='request_count', color_discrete_sequence=[COLORS["primary"]])
        st.plotly_chart(style_chart(fig_traffic), use_container_width=True)

with col_t2:
    st.subheader("Error Rate (%)")
    if not traffic_df.empty:
        fig_error = px.area(traffic_df, x='time', y='error_rate', color_discrete_sequence=[COLORS["accent"]])
        st.plotly_chart(style_chart(fig_error), use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# 3. Latency & Breakdown
col_p1, col_p2 = st.columns(2)
with col_p1:
    st.subheader("Average Latency")
    if not latency_df.empty:
        fig_lat = px.area(latency_df, x='time', y='avg_latency', color_discrete_sequence=[COLORS["secondary"]])
        st.plotly_chart(style_chart(fig_lat), use_container_width=True)

with col_p2:
    st.subheader("Services by Error Rate")
    if not service_df.empty:
        fig_svc = px.bar(service_df.sort_values('error_rate', ascending=False), x='service_name', y='error_rate', color_discrete_sequence=[COLORS["accent"]])
        fig_svc.update_layout(xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))
        st.plotly_chart(style_chart(fig_svc), use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# 4. Incident Log
st.subheader("Recent Incident Log")
if not incidents_df.empty:
    display_df = incidents_df.copy()
    display_df['detected_at'] = display_df['detected_at'].dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.success("System Healthy: No incidents recorded.")

# Handle Auto-Refresh
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
