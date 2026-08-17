# Log Schema — Incident/Log Anomaly Detector

Status: LOCKED — agreed by both team members. Treat any further change as a
breaking change requiring a re-sync between both sides.

## Purpose
This is the shared contract between the sample app (Person B) and the ingestion
pipeline (Person A). Every log line the sample app emits must match this shape.
Every downstream consumer (BigQuery schema, anomaly detection logic, dashboard)
reads against this shape.

## Field List

| Field         | Type      | Required | Description                                                                 |
|---------------|-----------|----------|-------------------------------------------------------------------------------|
| timestamp     | string (ISO 8601, UTC) | Yes | When the event occurred. e.g. `2026-08-17T09:32:11.204Z` |
| request_id    | string (UUID)          | Yes | Unique ID per request. Lets you trace one request end-to-end in the demo. |
| service_name  | string                  | Yes | Which part of the sample app handled it. e.g. `cart-service`, `checkout-service`, `auth-service` |
| endpoint      | string                  | Yes | Route/path hit. e.g. `/api/cart/add`, `/api/checkout` |
| method        | string                  | Yes | HTTP method. e.g. `GET`, `POST` |
| status_code   | integer                 | Yes | HTTP status returned. e.g. `200`, `404`, `500` |
| log_level     | string (enum)           | Yes | One of `INFO`, `WARN`, `ERROR` |
| latency_ms    | float                   | Yes | How long the request took to handle, in milliseconds |
| message       | string                  | Yes | Human-readable description. e.g. `"Order placed successfully"`, `"Payment gateway timeout"` |
| user_id       | string                  | No  | Simulated user identifier, if relevant to the request |
| error_type    | string                  | No  | Populated only when log_level = ERROR. e.g. `"TimeoutError"`, `"ValidationError"` |

## Naming Convention
`snake_case` for all field names, across every layer (sample app output, BigQuery
columns, Cloud Function code, Python detection code). No mixed casing.

## Timezone
All timestamps are UTC, everywhere in the system (sample app, BigQuery, Cloud
Function, detection logic). Convert to local time only in the dashboard display
layer, never in storage or in any intermediate processing step.

## Anomaly Detection Scope
Anomaly detection (z-score / moving average) runs on a **global** basis —
one rolling window across all logs combined, not split per service. This is a
deliberate scope decision given the internship timeline: synthetic demo
traffic and injected anomalies can be sized to trigger clearly on a global
threshold, avoiding the added complexity of per-service baselining (grouping,
per-group statistics, handling low-traffic services with noisy baselines).
Per-service thresholds are a documented possible enhancement for week 7-8
polish if time allows — not required for the core build.

## Example Payload

```json
{
  "timestamp": "2026-08-17T09:32:11.204Z",
  "request_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "service_name": "checkout-service",
  "endpoint": "/api/checkout",
  "method": "POST",
  "status_code": 500,
  "log_level": "ERROR",
  "latency_ms": 4032.5,
  "message": "Payment gateway timeout",
  "user_id": "user_00219",
  "error_type": "TimeoutError"
}
```

## Notes for Detection Logic (Person B)
- `timestamp` + `status_code` → error rate per time window (bucket by minute)
- `timestamp` + `latency_ms` → latency spike detection (z-score / moving average)
- `service_name` lets you optionally break anomalies down per service, not just
  globally, if there's time for that later
- `request_id` lets the incident summary reference a specific example request,
  not just "errors spiked" — makes the Vertex AI summary more concrete

## Notes for Ingestion Pipeline (Person A)
- Dead-letter handling: any log missing a required field (timestamp,
  request_id, service_name, endpoint, method, status_code, log_level,
  latency_ms, message) should be routed to a dead-letter table/topic, not
  silently dropped or silently inserted with nulls
- BigQuery table schema should mirror this field list directly — same names, same types

## Status
Reviewed and agreed by both team members. Locked as of today — treat any
further change as a breaking change requiring a re-sync between both sides.