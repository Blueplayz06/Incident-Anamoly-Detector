# Dashboard Setup — Looker Studio

Looker Studio has no Terraform/API-driven setup — this is a manual build
in the UI, but every chart below is fully specified: which data source,
which fields, which chart type, so it's execution, not design.

**Prerequisite:** `terraform apply` must have run for real — this dashboard
connects to the real `app_logs` and `incidents` BigQuery tables, not the
local emulator.

## Step 1 — Connect the data source

1. Go to https://lookerstudio.google.com
2. Create → Data Source → BigQuery
3. Select project: `jio-cloud-training`, dataset: `incident_logs`
4. Add **two** data sources: one for `app_logs`, one for `incidents`
5. Authorize access, connect

## Step 2 — Create the report

Create → Report → select both data sources added above.

## Panel 1 — Request Volume Over Time
- **Data source:** `app_logs`
- **Chart type:** Time series chart
- **Dimension:** `timestamp` (set to Date & Time, granularity: Minute or Hour depending on data volume)
- **Metric:** Record Count
- **Title:** "Request Volume"

## Panel 2 — Error Rate Over Time
- **Data source:** `app_logs`
- **Chart type:** Time series chart
- **Dimension:** `timestamp`
- **Metric:** Create a calculated field:
  ```
  COUNT_DISTINCT(CASE WHEN log_level = "ERROR" THEN request_id END) / COUNT(request_id)
  ```
  Name it `error_rate`, format as Percent.
- **Title:** "Error Rate"

## Panel 3 — Average Latency Over Time
- **Data source:** `app_logs`
- **Chart type:** Time series chart
- **Dimension:** `timestamp`
- **Metric:** `latency_ms` — Aggregation: Average
- **Title:** "Average Latency (ms)"
- Optional: add a second metric, `latency_ms` with Aggregation: Percentile (95th), to show p95 alongside average.

## Panel 4 — Status Code Breakdown
- **Data source:** `app_logs`
- **Chart type:** Pie chart or Donut chart
- **Dimension:** `status_code`
- **Metric:** Record Count
- **Title:** "Status Code Distribution"

## Panel 5 — Per-Service Breakdown
- **Data source:** `app_logs`
- **Chart type:** Bar chart
- **Dimension:** `service_name`
- **Metric:** Record Count (primary bar), plus a calculated `error_rate` field (same formula as Panel 2) as a second metric for comparison
- **Title:** "Requests & Error Rate by Service"

## Panel 6 — Recent Incidents (Table)
- **Data source:** `incidents`
- **Chart type:** Table
- **Dimensions/columns, in this order:**
  `detected_at`, `anomaly_type`, `service_name`, `current_value`,
  `baseline_value`, `z_score`, `summary`, `alert_sent`
- **Sort:** `detected_at`, descending (most recent first)
- **Title:** "Recent Incidents"
- Tip: widen the `summary` column since it contains full sentences.

## Panel 7 — Incident Count Over Time (optional but recommended)
- **Data source:** `incidents`
- **Chart type:** Time series or bar chart
- **Dimension:** `detected_at`
- **Metric:** Record Count
- **Title:** "Incidents Over Time"
- Gives an at-a-glance view of whether incidents are increasing/decreasing over the demo period.

## Step 3 — Layout suggestion

- Top row: Panel 1 (volume) and Panel 2 (error rate) side by side
- Second row: Panel 3 (latency) and Panel 4 (status codes) side by side
- Third row: Panel 5 (per-service) full width
- Bottom: Panel 6 (recent incidents table) full width, since it needs the most horizontal space
- Panel 7 can go wherever fits, or as a small addition near Panel 6

## Step 4 — Add a date range control

Insert → Date range control, placed at the top of the report, applied to
all charts — lets you (or a grader/reviewer) filter to the demo window
specifically instead of all historical data.

## Notes

- This connects to real GCP data — it will show nothing meaningful until
  `terraform apply` has run and the sample app has generated real traffic
  against the real pipeline (not the local emulator).
- Person B: feel free to change chart types, add panels, or adjust this
  layout — this spec is a complete starting point, not a fixed design.
  The one thing not to change is the underlying BigQuery field names,
  since those are locked in docs/schema.md and infra/terraform/bigquery.tf.
