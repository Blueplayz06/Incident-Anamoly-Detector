git #!/usr/bin/env bash
# Run from app/detector-service/ in Cloud Shell.
set -euo pipefail
PROJECT=jio-cloud-training
REGION=us-west1
SA=868369668937-compute@developer.gserviceaccount.com

# Reuse the existing modules instead of maintaining copies (don't commit the copies).
cp ../detection/incidents_store.py ../detection/vertex_summary.py .

# Queries need jobs.create; bigquery.dataEditor alone does NOT include it.
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" --role="roles/bigquery.jobUser"

gcloud functions deploy anomaly-detector --gen2 --region=$REGION \
  --runtime=python312 --source=. --entry-point=run_detection \
  --trigger-http --no-allow-unauthenticated --service-account=$SA

gcloud run services add-iam-policy-binding anomaly-detector --region=$REGION \
  --member="serviceAccount:$SA" --role="roles/run.invoker"

URL=$(gcloud functions describe anomaly-detector --gen2 --region=$REGION \
  --format='value(serviceConfig.uri)')

gcloud services enable cloudscheduler.googleapis.com
gcloud scheduler jobs create http detector-job --location=$REGION \
  --schedule="* * * * *" --uri="$URL" --http-method=POST \
  --oidc-service-account-email=$SA --oidc-token-audience="$URL" \
|| gcloud scheduler jobs update http detector-job --location=$REGION \
  --schedule="* * * * *" --uri="$URL" --http-method=POST \
  --oidc-service-account-email=$SA --oidc-token-audience="$URL"

echo "Deployed. Dry-run test:"
echo "curl -H \"Authorization: Bearer \$(gcloud auth print-identity-token --audiences=$URL)\" \"$URL?dry_run=1\""
