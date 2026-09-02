# --- Log-based metric: counts ERROR-level log entries ---
# This is a separate, simpler signal from the custom z-score anomaly
# detection (which runs in the detection Cloud Function). Cloud Monitoring
# can't natively evaluate our custom statistical logic, so this acts as a
# basic safety-net alert (e.g. "error volume is unusually high") independent
# of the main detection → Vertex AI → Slack pipeline.

resource "google_logging_metric" "error_log_count" {
  name    = "error-log-count"
  project = var.project_id

  # Matches ERROR-level entries exported through the log sink defined in
  # pubsub_logging.tf — keep this filter consistent with that sink.
  filter = "resource.type=\"cloud_run_revision\" OR resource.type=\"cloud_function\" jsonPayload.log_level=\"ERROR\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# --- Notification channel ---
# Placeholder: email is the simplest to stand up without extra setup.
# Slack requires either OAuth-based integration (more setup) or a generic
# webhook channel pointed at the Slack incoming webhook URL — swap this
# out once the Slack app + webhook exists (see permissions doc).

resource "google_monitoring_notification_channel" "email_alert" {
  display_name = "Team Email Alerts"
  type         = "email"
  project      = var.project_id

  labels = {
    email_address = var.alert_email
  }
}

# --- Alert policy: fires when ERROR log volume crosses a threshold ---
# DEFERRED: this resource depends on real log data matching the log-based
# metric's filter (resource.type="cloud_run_revision" OR "cloud_function"),
# which only exists once the sample app is actually deployed to GCP as a
# Cloud Run service or Cloud Function. Since it currently runs locally
# against a Pub/Sub emulator, no logs have ever matched this filter, and
# Cloud Monitoring cannot validate/create an alert policy against a metric
# with zero established resource-type data ("supplied filter does not
# specify a valid combination of metric and monitored resource
# descriptors"). Re-enable this block once the sample app is deployed and
# generating real matching logs.
#
# resource "google_monitoring_alert_policy" "error_spike_alert" {
#   display_name = "Error Log Spike"
#   project      = var.project_id
#   combiner     = "OR"
#
#   conditions {
#     display_name = "Error log count above threshold"
#
#     condition_threshold {
#       filter          = "resource.type=\"global\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.error_log_count.name}\""
#       comparison      = "COMPARISON_GT"
#       threshold_value = var.error_alert_threshold
#       duration        = "60s"
#
#       aggregations {
#         alignment_period   = "60s"
#         per_series_aligner = "ALIGN_COUNT"
#       }
#     }
#   }
#
#   notification_channels = [google_monitoring_notification_channel.email_alert.id]
#
#   documentation {
#     content   = "Error log volume has crossed the configured threshold. Check the BigQuery app_logs table and dashboard for details. Note: this is a raw-count safety net, separate from the z-score anomaly detection pipeline."
#     mime_type = "text/markdown"
#   }
# }
