"""
Stateless anomaly detector for Cloud Functions (Gen 2, HTTP trigger).

Every invocation reads per-minute stats from BigQuery, compares the latest
complete minute against the preceding baseline, and (if anomalous and not
recently alerted) writes an incident + emits a structured ERROR log line
that a log-based metric turns into an email alert.

Test without side effects:  <function-url>?dry_run=1
"""

import json
import os
import statistics

import functions_framework
from google.cloud import bigquery

from incidents_store import write_incident
from vertex_summary import generate_incident_summary

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "jio-cloud-training")
DATASET_ID = "incident_logs"
LOGS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.app_logs"
INCIDENTS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.incidents"

BASELINE_MINUTES = int(os.environ.get("BASELINE_MINUTES", "30"))
MIN_BASELINE_BUCKETS = int(os.environ.get("MIN_BASELINE_BUCKETS", "10"))
MIN_LOGS_PER_BUCKET = int(os.environ.get("MIN_LOGS_PER_BUCKET", "5"))
Z_THRESHOLD = float(os.environ.get("Z_THRESHOLD", "3.0"))
COOLDOWN_MINUTES = int(os.environ.get("COOLDOWN_MINUTES", "5"))

LATENCY_SD_FLOOR_FRAC = 0.05   # 5% of baseline mean, at least 1 ms
ERROR_RATE_SD_FLOOR = 0.01     # 1 percentage point

_bq = None


def bq():
    global _bq
    if _bq is None:
        _bq = bigquery.Client(project=PROJECT_ID)
    return _bq


def fetch_buckets():
    """Last BASELINE_MINUTES+1 complete minutes, oldest first."""
    sql = f"""
    SELECT
      TIMESTAMP_TRUNC(timestamp, MINUTE) AS bucket,
      COUNT(*) AS n,
      AVG(latency_ms) AS avg_latency,
      COUNTIF(log_level = 'ERROR') / COUNT(*) AS error_rate
    FROM `{LOGS_TABLE}`
    WHERE timestamp >= TIMESTAMP_SUB(TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MINUTE),
                                     INTERVAL @mins MINUTE)
      AND timestamp <  TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MINUTE)
    GROUP BY bucket
    ORDER BY bucket
    """
    cfg = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("mins", "INT64", BASELINE_MINUTES + 1)
        ]
    )
    return [dict(r) for r in bq().query(sql, job_config=cfg).result()]


def latest_complete_minute():
    row = list(bq().query(
        "SELECT TIMESTAMP_SUB(TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MINUTE), "
        "INTERVAL 1 MINUTE) AS t"
    ).result())[0]
    return row["t"]


def z_check(current, history, sd_floor):
    """Returns (baseline_mean, z_score). Upper outliers already in the
    baseline are trimmed once so a past incident doesn't inflate the threshold."""
    hist = list(history)
    mean = statistics.mean(hist)
    sd = statistics.stdev(hist) if len(hist) > 1 else 0.0

    kept = [v for v in hist if v <= mean + Z_THRESHOLD * max(sd, sd_floor(mean))]
    if 3 <= len(kept) < len(hist):
        hist = kept
        mean = statistics.mean(hist)
        sd = statistics.stdev(hist)

    sd = max(sd, sd_floor(mean))
    return mean, (current - mean) / sd


def recently_alerted(anomaly_type):
    sql = f"""
    SELECT COUNT(*) AS c FROM `{INCIDENTS_TABLE}`
    WHERE anomaly_type = @t
      AND detected_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @m MINUTE)
    """
    cfg = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("t", "STRING", anomaly_type),
            bigquery.ScalarQueryParameter("m", "INT64", COOLDOWN_MINUTES),
        ]
    )
    return list(bq().query(sql, job_config=cfg).result())[0]["c"] > 0


def raise_incident(anomaly_type, current, baseline, z):
    summary = generate_incident_summary(
        service_name="all-services",
        anomaly_type=anomaly_type,
        current_value=current,
        baseline_value=baseline,
        z_score=z,
    )
    # Structured line -> Cloud Logging jsonPayload -> log-based metric -> email.
    print(json.dumps({
        "severity": "ERROR",
        "message": "ANOMALY_DETECTED",
        "anomaly_type": anomaly_type,
        "current_value": current,
        "baseline_value": baseline,
        "z_score": z,
        "summary": summary,
    }))
    write_incident(
        anomaly_type=anomaly_type,
        service_name="all-services",
        current_value=current,
        baseline_value=baseline,
        z_score=z,
        summary=summary,
        alert_sent=True,  # alert log line emitted; email delivery is Monitoring's job
    )


@functions_framework.http
def run_detection(request):
    dry_run = request.args.get("dry_run") == "1"
    buckets = fetch_buckets()
    expected = latest_complete_minute()

    if not buckets or buckets[-1]["bucket"] != expected or buckets[-1]["n"] < MIN_LOGS_PER_BUCKET:
        return {"status": "skipped", "reason": "no/low traffic in latest complete minute"}, 200

    current = buckets[-1]
    baseline = [b for b in buckets[:-1] if b["n"] >= MIN_LOGS_PER_BUCKET]
    if len(baseline) < MIN_BASELINE_BUCKETS:
        return {"status": "skipped",
                "reason": f"baseline too small ({len(baseline)}/{MIN_BASELINE_BUCKETS} usable minutes)"}, 200

    checks = {
        "latency": (float(current["avg_latency"]), [float(b["avg_latency"]) for b in baseline],
                    lambda m: max(m * LATENCY_SD_FLOOR_FRAC, 1.0)),
        "error_rate": (float(current["error_rate"]), [float(b["error_rate"]) for b in baseline],
                       lambda m: ERROR_RATE_SD_FLOOR),
    }

    results = {}
    for name, (cur, hist, floor) in checks.items():
        mean, z = z_check(cur, hist, floor)
        is_anomaly = z > Z_THRESHOLD
        action = "none"
        if is_anomaly:
            if dry_run:
                action = "would_alert (dry run)"
            elif recently_alerted(name):
                action = "suppressed (cooldown)"
            else:
                raise_incident(name, cur, mean, z)
                action = "alerted"
        results[name] = {"current": round(cur, 4), "baseline_mean": round(mean, 4),
                         "z": round(z, 2), "anomaly": is_anomaly, "action": action}

    return {"status": "ok", "minute": expected.isoformat(),
            "logs_in_minute": current["n"], "baseline_minutes": len(baseline),
            "results": results}, 200
