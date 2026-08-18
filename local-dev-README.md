# Local Development Setup

This lets you test against a local Pub/Sub emulator instead of the real GCP
project — no cost, no risk of triggering resource-creation alerts, and works
offline.

## Start the emulator

```bash
docker compose up -d pubsub-emulator
```

## Point your code at the emulator instead of real GCP

Set this environment variable before running any Python/Node code that uses
the Pub/Sub client library:

```bash
export PUBSUB_EMULATOR_HOST=localhost:8085
export GOOGLE_CLOUD_PROJECT=local-dev-project
```

(PowerShell equivalent:)
```powershell
$env:PUBSUB_EMULATOR_HOST = "localhost:8085"
$env:GOOGLE_CLOUD_PROJECT = "local-dev-project"
```

When these are set, the Pub/Sub client libraries automatically talk to the
local emulator instead of real GCP — no code changes needed, no real
credentials needed.

## Create a topic/subscription on the emulator for testing

```bash
gcloud beta emulators pubsub env-init  # prints env vars, or set manually as above

# then use gcloud as normal, it'll hit the emulator:
gcloud pubsub topics create log-ingestion-topic --project=local-dev-project
gcloud pubsub subscriptions create log-ingestion-sub --topic=log-ingestion-topic --project=local-dev-project
```

## Stop the emulator

```bash
docker compose down
```

## Notes

- Emulator data is not persisted between restarts — fine for dev/testing,
  don't rely on it for anything you need to keep.
- The sample-app and ingestion-function services in docker-compose.yml are
  commented out until they have Dockerfiles — uncomment as they're built.
