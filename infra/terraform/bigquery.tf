# --- BigQuery dataset ---

resource "google_bigquery_dataset" "logs" {
  dataset_id  = "incident_logs"
  project     = var.project_id
  location    = var.region
  description = "Stores parsed application logs for anomaly detection"
}

# --- Main log table — schema mirrors docs/schema.md exactly ---
# Required fields per schema doc: timestamp, request_id, service_name,
# endpoint, method, status_code, log_level, latency_ms, message
# Optional: user_id, error_type

resource "google_bigquery_table" "logs" {
  dataset_id = google_bigquery_dataset.logs.dataset_id
  table_id   = "app_logs"
  project    = var.project_id

  schema = jsonencode([
    { name = "timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "request_id", type = "STRING", mode = "REQUIRED" },
    { name = "service_name", type = "STRING", mode = "REQUIRED" },
    { name = "endpoint", type = "STRING", mode = "REQUIRED" },
    { name = "method", type = "STRING", mode = "REQUIRED" },
    { name = "status_code", type = "INTEGER", mode = "REQUIRED" },
    { name = "log_level", type = "STRING", mode = "REQUIRED" },
    { name = "latency_ms", type = "FLOAT", mode = "REQUIRED" },
    { name = "message", type = "STRING", mode = "REQUIRED" },
    { name = "user_id", type = "STRING", mode = "NULLABLE" },
    { name = "error_type", type = "STRING", mode = "NULLABLE" }
  ])

  # Partitioning by timestamp keeps queries over specific time windows
  # (which is what anomaly detection does — rolling windows) fast and cheap.
  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }
}

# --- Dead-letter table — logs that failed required-field validation ---
# Matches the dead-letter handling principle from docs/schema.md.

resource "google_bigquery_table" "logs_dead_letter" {
  dataset_id = google_bigquery_dataset.logs.dataset_id
  table_id   = "app_logs_dead_letter"
  project    = var.project_id

  schema = jsonencode([
    { name = "raw_payload", type = "STRING", mode = "REQUIRED", description = "Original unparsed log payload" },
    { name = "received_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "error_reason", type = "STRING", mode = "NULLABLE", description = "Why the payload was rejected, e.g. missing required field" }
  ])

  time_partitioning {
    type  = "DAY"
    field = "received_at"
  }
}

# --- Incidents table — every confirmed anomaly detection fires a row here ---
# This is what the dashboard's "recent incidents" panel reads from. Written
# to by anomaly_detector.py's handle_anomaly() function.

resource "google_bigquery_table" "incidents" {
  dataset_id = google_bigquery_dataset.logs.dataset_id
  table_id   = "incidents"
  project    = var.project_id

  schema = jsonencode([
    { name = "incident_id", type = "STRING", mode = "REQUIRED", description = "Unique ID for this incident" },
    { name = "detected_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "anomaly_type", type = "STRING", mode = "REQUIRED", description = "latency or error_rate" },
    { name = "service_name", type = "STRING", mode = "REQUIRED", description = "Service the anomaly relates to — 'all-services' under the current global-threshold design" },
    { name = "current_value", type = "FLOAT", mode = "REQUIRED" },
    { name = "baseline_value", type = "FLOAT", mode = "REQUIRED" },
    { name = "z_score", type = "FLOAT", mode = "REQUIRED" },
    { name = "summary", type = "STRING", mode = "REQUIRED", description = "Generated incident summary (Vertex AI or templated fallback)" },
    { name = "alert_sent", type = "BOOLEAN", mode = "REQUIRED", description = "Whether the Slack/email alert was successfully delivered" }
  ])

  time_partitioning {
    type  = "DAY"
    field = "detected_at"
  }
}
