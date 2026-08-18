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
