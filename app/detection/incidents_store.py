"""
Writes confirmed anomaly detections to the BigQuery incidents table, so
the dashboard has real, queryable incident history to display.

Lazily initializes the BigQuery client (same pattern as main.py) so this
stays importable/testable without live GCP credentials when not actually
writing.
"""

import os
import uuid
from datetime import datetime, timezone

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "jio-cloud-training")
DATASET_ID = "incident_logs"
TABLE_ID = "incidents"

_bq_client = None


def _get_bq_client():
    global _bq_client
    if _bq_client is None:
        from google.cloud import bigquery
        _bq_client = bigquery.Client(project=PROJECT_ID)
    return _bq_client


def write_incident(
    anomaly_type: str,
    service_name: str,
    current_value: float,
    baseline_value: float,
    z_score: float,
    summary: str,
    alert_sent: bool,
) -> bool:
    """
    Writes one incident row to BigQuery. Returns True on success, False on
    failure — never raises, so a BigQuery write issue doesn't crash the
    detection loop (same graceful-degradation pattern as notifications.py
    and vertex_summary.py).
    """
    row = {
        "incident_id": str(uuid.uuid4()),
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "anomaly_type": anomaly_type,
        "service_name": service_name,
        "current_value": current_value,
        "baseline_value": baseline_value,
        "z_score": z_score,
        "summary": summary,
        "alert_sent": alert_sent,
    }

    try:
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
        errors = _get_bq_client().insert_rows_json(table_ref, [row])
        if errors:
            print(f"Failed to write incident to BigQuery: {errors}")
            return False
        return True
    except Exception as e:
        print(f"Failed to write incident to BigQuery (client error): {e}")
        return False
