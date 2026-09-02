# --- Alert policy: fires when ERROR log volume crosses a threshold ---
# Starting threshold is intentionally simple (raw count over a short
# window) — tune once real traffic patterns from the sample app are known.

resource "google_monitoring_alert_policy" "error_spike_alert" {
  display_name = "Error Log Spike"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Error log count above threshold"

    condition_threshold {
      filter          = "resource.type=\"global\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.error_log_count.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.error_alert_threshold
      duration        = "60s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email_alert.id]

  documentation {
    content   = "Error log volume has crossed the configured threshold. Check the BigQuery app_logs table and dashboard for details. Note: this is a raw-count safety net, separate from the z-score anomaly detection pipeline."
    mime_type = "text/markdown"
  }
}
