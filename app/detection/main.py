"""
Ingestion Cloud Function — reads log messages from the Pub/Sub subscription,
validates them against the schema in docs/schema.md, and writes valid rows
to BigQuery. Malformed messages go to the dead-letter table.

Local testing: run against the Pub/Sub emulator (see /local-dev-README.md)
before deploying for real.
"""

import base64
import json
import os
from datetime import datetime, timezone

from google.cloud import bigquery

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "jio-cloud-training")
DATASET_ID = "incident_logs"
TABLE_ID = "app_logs"
DEAD_LETTER_TABLE_ID = "app_logs_dead_letter"

# Required fields per docs/schema.md — a message missing any of these
# goes to the dead-letter table instead of the main table.
REQUIRED_FIELDS = [
    "timestamp",
    "request_id",
    "service_name",
    "endpoint",
    "method",
    "status_code",
    "log_level",
    "latency_ms",
    "message",
]

_bq_client = None


def get_bq_client():
    """Lazily creates the BigQuery client on first real use, instead of at
    module import time — keeps validate_log and other pure-logic pieces
    testable without needing real GCP credentials."""
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=PROJECT_ID)
    return _bq_client


def validate_log(payload: dict) -> tuple[bool, str]:
    """Returns (is_valid, error_reason)."""
    missing = [f for f in REQUIRED_FIELDS if f not in payload or payload[f] is None]
    if missing:
        return False, f"Missing required field(s): {', '.join(missing)}"

    if not isinstance(payload.get("status_code"), int):
        return False, "status_code must be an integer"

    if not isinstance(payload.get("latency_ms"), (int, float)):
        return False, "latency_ms must be a number"

    if payload.get("log_level") not in ("INFO", "WARN", "ERROR"):
        return False, f"Invalid log_level: {payload.get('log_level')}"

    return True, ""


def write_to_bigquery(table_id: str, rows: list[dict]) -> None:
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_id}"
    errors = get_bq_client().insert_rows_json(table_ref, rows)
    if errors:
        # In production this should go somewhere more durable than a log
        # line (e.g. Cloud Monitoring alert) — logged for now, revisit
        # once alerting is built.
        print(f"BigQuery insert errors for {table_id}: {errors}")


def process_log_message(event, context):
    """
    Pub/Sub-triggered Cloud Function entry point.
    `event` contains the Pub/Sub message; the actual payload is
    base64-encoded in event['data'].
    """
    raw_data = base64.b64decode(event["data"]).decode("utf-8")

    try:
        payload = json.loads(raw_data)
    except json.JSONDecodeError as e:
        write_to_bigquery(
            DEAD_LETTER_TABLE_ID,
            [
                {
                    "raw_payload": raw_data,
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "error_reason": f"Invalid JSON: {e}",
                }
            ],
        )
        return

    is_valid, error_reason = validate_log(payload)

    if not is_valid:
        write_to_bigquery(
            DEAD_LETTER_TABLE_ID,
            [
                {
                    "raw_payload": raw_data,
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "error_reason": error_reason,
                }
            ],
        )
        return

    row = {
        "timestamp": payload["timestamp"],
        "request_id": payload["request_id"],
        "service_name": payload["service_name"],
        "endpoint": payload["endpoint"],
        "method": payload["method"],
        "status_code": payload["status_code"],
        "log_level": payload["log_level"],
        "latency_ms": payload["latency_ms"],
        "message": payload["message"],
        "user_id": payload.get("user_id"),
        "error_type": payload.get("error_type"),
    }

    write_to_bigquery(TABLE_ID, [row])