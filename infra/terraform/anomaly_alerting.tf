# Alerting for the anomaly-detector function: it prints a structured
# ANOMALY_DETECTED ERROR line; this counts those lines and emails on any.

resource "google_logging_metric" "anomaly_detected_count" {
  name        = "anomaly-detected-count"
  description = "Counts ANOMALY_DETECTED log lines emitted by the anomaly-detector function"
  filter      = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"anomaly-detector\" AND jsonPayload.message=\"ANOMALY_DETECTED\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_alert_policy" "anomaly_detected" {
  display_name = "Anomaly detected (incident detector)"
  combiner     = "OR"

  conditions {
    display_name = "ANOMALY_DETECTED log line seen"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.anomaly_detected_count.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email_alert.id]

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "The anomaly detector flagged a latency or error-rate spike. Details and summary: BigQuery table incident_logs.incidents."
    mime_type = "text/markdown"
  }
}
