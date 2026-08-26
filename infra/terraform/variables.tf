variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "jio-cloud-training"
}

variable "region" {
  description = "GCP region for all resources. Locked to us-west1 due to an org-level resourceLocations policy on this project — see docs/adr.md or team notes for details. Do not change without confirming the org policy allows a different region."
  type        = string
  default     = "us-west1"
}

variable "alert_email" {
  description = "Email address to receive Cloud Monitoring alerts. Update with the team's actual monitoring email before applying."
  type        = string
  default     = "devansh.nayak@ril.com"
}

variable "error_alert_threshold" {
  description = "Number of ERROR-level logs in a 60s window that triggers an alert. Starting value — tune once real sample-app traffic patterns are known."
  type        = number
  default     = 10
}
