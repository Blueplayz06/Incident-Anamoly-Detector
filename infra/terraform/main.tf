	terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Remote state backend — points at the GCS bucket created for this project.
  # NOTE: bucket name below is a placeholder. Update once the real state
  # bucket is created (gsutil mb -l us-west1 gs://<project>-tfstate/), and
  # do not run `terraform init` against this backend until that bucket
  # actually exists.
  backend "gcs" {
    bucket = "jio-cloud-training-tfstate"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
