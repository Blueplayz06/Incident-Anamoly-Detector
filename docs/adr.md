# ADR 001: Pub/Sub + Cloud Functions over GKE + Kafka

Status: Accepted
Date: 2026-08-18

## Context

The pipeline needs to ingest application logs, move them from Cloud Logging
through to BigQuery, and trigger anomaly detection and alerting. Two
realistic architectural options were considered for the ingestion/messaging
layer:

1. **Pub/Sub + Cloud Functions** — GCP-native, fully managed, serverless
2. **Kafka on GKE** — self-managed messaging on a Kubernetes cluster

The team has hands-on experience with both Kubernetes and Kafka from prior
work, so this wasn't a case of picking the option we knew — both were
genuinely available choices.

## Decision

We chose **Pub/Sub + Cloud Functions**.

## Reasoning

- **Operational overhead.** GKE + Kafka requires managing a cluster —
  node pools, scaling, upgrades, Kafka broker configuration, topic
  partitioning — on top of building the actual anomaly detection logic.
  For a 2-person team on a fixed timeline, that overhead competes directly
  with time spent on the features that make this project demonstrable
  (detection logic, incident summaries, dashboard).
- **Fully managed, serverless fits the project's scale.** This project
  processes logs from a single sample e-commerce app, not production-scale
  traffic. Pub/Sub and Cloud Functions scale to zero when idle and require
  no capacity planning, which matches a demo/portfolio project's actual
  load profile.
- **Cloud-native GCP story.** Part of the goal of this project is
  demonstrating GCP-specific infrastructure skills for a
  cloud/infrastructure-focused career track. Pub/Sub, Cloud Functions,
  Cloud Logging sinks, and BigQuery are all GCP-managed services with
  direct IAM integration — this tells a more GCP-native infrastructure
  story than running Kafka on GKE, which is a portable pattern that
  doesn't showcase GCP's managed service ecosystem specifically.
- **Faster to a working end-to-end pipeline.** Cloud Logging sinks export
  directly to Pub/Sub with a few lines of Terraform. Standing up Kafka on
  GKE (even managed via GKE Autopilot) involves considerably more setup
  before the first log even reaches storage.

## Consequences

- We give up some flexibility Kafka offers (e.g., log replay across
  arbitrary time windows, more granular consumer group control) — not
  needed for this project's scope.
- We are tied more tightly to GCP-specific services, which is an accepted
  tradeoff given the project's explicit goal of demonstrating GCP
  infrastructure skills.
- If traffic or scope grew significantly beyond a demo (e.g., a real
  multi-service production system), Kafka on GKE would likely become the
  stronger choice — noted here as a legitimate future direction, not a
  weakness of the current decision for this project's actual scope.

## Alternatives Considered

**Kafka on GKE** — rejected for this project due to operational overhead
disproportionate to project scale and timeline, despite team familiarity
with both technologies.
