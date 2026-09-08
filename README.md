# Incident/Log Anomaly Detector

A GCP-based automated incident and log anomaly detection system, built as a
2-person internship project. Ingests application logs from a sample
e-commerce app, detects anomalies (error spikes, latency spikes) using
statistical methods, and auto-generates incident summaries with alerts.

## What it does

1. A sample e-commerce app generates logs (normal traffic + injectable
   error/latency spikes)
2. Logs are exported via a Cloud Logging sink into Pub/Sub
3. A Cloud Function parses and validates each log, writing valid entries to
   BigQuery (malformed entries go to a dead-letter table)
4. Statistical anomaly detection (z-score / moving average) runs against
   the log stream, with alert deduplication so an ongoing incident doesn't
   re-alert every window
5. When an anomaly is detected, a summary is generated and the incident is
   recorded in BigQuery
6. An email alert is sent and the incident appears on a dashboard

## Architecture

```
Sample App → Cloud Logging → Pub/Sub → Cloud Function (parse/validate)
    → BigQuery → Anomaly Detection → Incident Summary → Alert → Dashboard
```

See [`docs/adr.md`](docs/adr.md) for the reasoning behind key architecture
decisions (Pub/Sub + Cloud Functions over GKE + Kafka; deferred
per-component service accounts).

![Architecture diagram](docs/architecture-diagram.svg)

## Team

- **Person A (Infra & Pipeline):** GCP setup, Cloud Logging sink, Pub/Sub,
  ingestion Cloud Function, BigQuery, Cloud Monitoring/alerting, Terraform,
  CI/CD, notification delivery
- **Person B (App, Logic & Presentation):** Sample log-generating app,
  anomaly detection logic, incident summaries, dashboard

## Repo structure

```
├── .github/workflows/     — CI (Python tests + Terraform validation on every PR)
├── app/
│   ├── sample-app/         — sample e-commerce app + traffic generator
│   ├── detection/           — ingestion Cloud Function, anomaly detector,
│   │                          incident summary generation, notifications
│   └── dashboard/            — dashboard (Looker Studio config / assets)
├── docs/
│   ├── schema.md             — locked log schema, the contract between app and pipeline
│   ├── adr.md                 — architecture decision records
│   ├── dashboard-setup.md      — Looker Studio setup spec
│   └── architecture-diagram.svg
├── infra/
│   └── terraform/              — infrastructure as code (Pub/Sub, BigQuery, Monitoring, etc.)
├── docker-compose.yml          — local dev setup (Pub/Sub emulator)
└── local-dev-README.md         — how to run the local dev environment
```

## Local development

See [`local-dev-README.md`](local-dev-README.md) for running against a
local Pub/Sub emulator instead of real GCP — no cost, no cloud credentials
needed for basic testing.

Quick start (four terminals):

```bash
# 1. Start the emulator
docker compose up -d pubsub-emulator

# 2. Sample app (app/sample-app)
export PUBSUB_EMULATOR_HOST=localhost:8085
export GOOGLE_CLOUD_PROJECT=local-dev-project
python3 -m uvicorn main:app --reload --port 8000

# 3. Traffic generator (app/sample-app)
python3 traffic_generator.py

# 4. Anomaly detector (app/detection)
python3 anomaly_detector.py
```

Trigger a demo anomaly:

```bash
curl -X POST http://localhost:8000/admin/trigger-error-burst
curl -X POST http://localhost:8000/admin/stop-error-burst
```

This full chain — traffic → detection → incident summary → alert attempt
→ incident recorded — has been run and verified locally end-to-end.

## Log schema

All log entries follow the schema defined in
[`docs/schema.md`](docs/schema.md). This is the contract between the
sample app and the ingestion pipeline — any change to it needs to be
agreed by both team members before code is updated.

## Infrastructure

All GCP infrastructure is managed via Terraform in `infra/terraform/`.
Resources are pinned to `us-west1` due to an org-level resource-location
policy on the GCP project — see `infra/terraform/variables.tf` for details.

**Applied and live on GCP:** BigQuery dataset and tables (`app_logs`,
`incidents`, `app_logs_dead_letter`), Pub/Sub topic/subscription/DLQ,
Cloud Logging sink, log-based error metric, email notification channel.

**Deferred:** the Cloud Monitoring alert policy — it depends on real logs
matching its filter (`cloud_run_revision` or `cloud_function` resource
types), which only exist once the sample app is deployed to GCP. See the
comment in `infra/terraform/monitoring.tf` for details. Will be re-enabled
once the sample app is deployed.

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR to
`main`:

- Python unit tests for the ingestion function
- Terraform format check + validate (no live GCP calls — credentials
  aren't wired into CI yet)

`main` is branch-protected — changes go through a PR with required review.

## Incident summaries

`app/detection/vertex_summary.py` generates incident summaries using a
deterministic, rule-based generator — this is the primary, supported
path, with no external API dependency or cost.

A real Vertex AI (Gemini) integration is also written and can be enabled
via `USE_LIVE_VERTEX_AI=true`, as an optional enhancement. As of testing,
this project's GCP setup doesn't have full generative-model access
enabled, so this path isn't currently verified working — if enabled and
the call fails for any reason, it automatically falls back to the
rule-based generator so the pipeline never breaks.

## Notifications

Alerting is delivered via email through the Cloud Monitoring alert policy
(`infra/terraform/monitoring.tf`), sent to the address configured in
`alert_email` (`infra/terraform/variables.tf`). This is the only alerting
path for this project — a team Slack workspace does not exist and is not
expected to be set up.

## Security notes

A repo-wide check (commit history, `.gitignore` coverage, committed
files) found no exposed secrets or credential files. Per-component
service accounts (one scoped identity per Cloud Function, rather than
shared defaults) were deliberately deferred — see
[ADR 002](docs/adr.md#adr-002-deferred--per-component-service-accounts)
for the reasoning and what a complete version would involve.

## Status

**Built and verified locally:**
- Sample app + traffic generator, generating realistic logs with
  injectable anomalies
- Ingestion Cloud Function (unit + integration tested)
- Anomaly detection with alert deduplication (rolling z-score on latency
  and error rate)
- Incident summary generation (rule-based; Vertex AI optional, not
  currently verified working)
- Incident recording to BigQuery (code complete, first real write pending
  sample app deployment)
- Email alerting (configured, live)
- Full pipeline wired and confirmed working end-to-end locally

**Live on real GCP:**
- BigQuery dataset + 3 tables, Pub/Sub + DLQ, logging sink, log-based
  metric, email notification channel (12 resources applied via Terraform)

**Deferred:**
- Cloud Monitoring alert policy (depends on sample app deployment)

**Not started:**
- Sample app deployment to GCP (Cloud Run)
- Dashboard (spec complete — see `docs/dashboard-setup.md` — build
  pending real data)
- Demo script and rehearsal