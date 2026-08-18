# --- Pub/Sub topic that receives exported logs ---

resource "google_pubsub_topic" "log_ingestion" {
  name    = "log-ingestion-topic"
  project = var.project_id

  # Retained for 7 days in case the ingestion Cloud Function needs to be
  # redeployed and replay recent messages.
  message_retention_duration = "604800s"
}

# --- Subscription the ingestion Cloud Function will read from ---
# Using a PULL subscription (decision: docs/adr.md or team notes) — simpler
# to run/debug locally than push, and doesn't require a public HTTPS
# endpoint for a project at this scale.

resource "google_pubsub_subscription" "log_ingestion_sub" {
  name    = "log-ingestion-sub"
  topic   = google_pubsub_topic.log_ingestion.name
  project = var.project_id

  ack_deadline_seconds = 60

  # Undelivered messages go here instead of being silently dropped —
  # matches the dead-letter handling principle from docs/schema.md.
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.log_ingestion_dlq.id
    max_delivery_attempts = 5
  }
}

# --- Dead-letter topic for malformed/undeliverable messages ---

resource "google_pubsub_topic" "log_ingestion_dlq" {
  name    = "log-ingestion-dlq"
  project = var.project_id
}

resource "google_pubsub_subscription" "log_ingestion_dlq_sub" {
  name    = "log-ingestion-dlq-sub"
  topic   = google_pubsub_topic.log_ingestion_dlq.name
  project = var.project_id
}

# --- Cloud Logging sink: exports logs from the sample app into the topic ---
# NOTE: the filter below is a starting point — narrow it once the sample
# app's actual log format/resource type is known, so we're not exporting
# unrelated project logs into the pipeline.

resource "google_logging_project_sink" "app_log_sink" {
  name        = "app-log-to-pubsub-sink"
  project     = var.project_id
  destination = "pubsub.googleapis.com/${google_pubsub_topic.log_ingestion.id}"

  filter = "resource.type=\"cloud_run_revision\" OR resource.type=\"cloud_function\""

  unique_writer_identity = true
}

# --- Grant the sink's writer identity permission to publish to the topic ---
# Required: log sinks write as their own service identity, not as you.

resource "google_pubsub_topic_iam_member" "sink_publisher" {
  topic   = google_pubsub_topic.log_ingestion.name
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = google_logging_project_sink.app_log_sink.writer_identity
}
