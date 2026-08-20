"""
Basic anomaly detection — pulls logs from the Pub/Sub subscription,
maintains a rolling baseline, and flags windows where latency or error
rate crosses a z-score threshold.

This is a deliberately simple first version — global threshold across all
services (per docs/schema.md decision), not per-service. Meant to prove
the detection concept works end-to-end; refine/replace as needed.

Run alongside the sample app + traffic generator:
    python anomaly_detector.py
"""

import json
import os
import statistics
import time
from collections import deque

from google.cloud import pubsub_v1

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "local-dev-project")
SUBSCRIPTION_ID = "log-ingestion-sub"

# How often to evaluate a window, in seconds.
WINDOW_SECONDS = 10

# How many past windows to keep as the rolling baseline.
BASELINE_WINDOW_COUNT = 6  # last ~60s of history

# z-score above this triggers an anomaly flag.
Z_SCORE_THRESHOLD = 3.0

subscriber = pubsub_v1.SubscriberClient()
publisher = pubsub_v1.PublisherClient()
sub_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)
topic_path = publisher.topic_path(PROJECT_ID, "log-ingestion-topic")


def ensure_topic_and_subscription_exist():
    """The emulator doesn't persist data across restarts — recreate the
    topic/subscription if they're missing rather than failing outright."""
    try:
        publisher.create_topic(request={"name": topic_path})
        print(f"Created topic: {topic_path}")
    except Exception:
        pass  # already exists

    try:
        subscriber.create_subscription(
            request={"name": sub_path, "topic": topic_path}
        )
        print(f"Created subscription: {sub_path}")
    except Exception:
        pass  # already exists

# Rolling history of past windows' stats, used as the baseline.
latency_history = deque(maxlen=BASELINE_WINDOW_COUNT)
error_rate_history = deque(maxlen=BASELINE_WINDOW_COUNT)


def pull_logs_for_window(duration_seconds: int) -> list[dict]:
    """Pulls whatever messages arrive during this window."""
    logs = []
    end_time = time.time() + duration_seconds

    while time.time() < end_time:
        response = subscriber.pull(
            request={"subscription": sub_path, "max_messages": 100},
            timeout=max(1, end_time - time.time()),
        )
        if not response.received_messages:
            continue

        ack_ids = []
        for received in response.received_messages:
            try:
                data = received.message.data.decode("utf-8")
                logs.append(json.loads(data))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # skip malformed — real dead-letter handling lives in the ingestion function
            ack_ids.append(received.ack_id)

        if ack_ids:
            subscriber.acknowledge(
                request={"subscription": sub_path, "ack_ids": ack_ids}
            )

    return logs


def compute_window_stats(logs: list[dict]) -> dict:
    if not logs:
        return {"count": 0, "avg_latency": 0, "error_rate": 0}

    latencies = [log.get("latency_ms", 0) for log in logs]
    error_count = sum(1 for log in logs if log.get("log_level") == "ERROR")

    return {
        "count": len(logs),
        "avg_latency": statistics.mean(latencies),
        "error_rate": error_count / len(logs),
    }


def check_anomaly(current_value: float, history: deque, label: str) -> bool:
    """Returns True if current_value is a z-score anomaly vs. history."""
    if len(history) < 3:
        return False  # not enough baseline data yet

    mean = statistics.mean(history)
    stdev = statistics.stdev(history) if len(history) > 1 else 0

    if stdev == 0:
        return False  # no variance to compare against

    z_score = (current_value - mean) / stdev

    if z_score > Z_SCORE_THRESHOLD:
        print(f"🚨 ANOMALY — {label}: current={current_value:.2f}, "
              f"baseline_mean={mean:.2f}, z_score={z_score:.2f}")
        return True

    return False


def run():
    print(f"Anomaly detector running — {WINDOW_SECONDS}s windows, "
          f"z-score threshold {Z_SCORE_THRESHOLD}. Ctrl+C to stop.\n")

    while True:
        logs = pull_logs_for_window(WINDOW_SECONDS)
        stats = compute_window_stats(logs)

        print(f"Window: {stats['count']} logs, "
              f"avg_latency={stats['avg_latency']:.2f}ms, "
              f"error_rate={stats['error_rate']:.2%}")

        latency_anomaly = check_anomaly(
            stats["avg_latency"], latency_history, "latency"
        )
        error_anomaly = check_anomaly(
            stats["error_rate"], error_rate_history, "error_rate"
        )

        if not latency_anomaly and not error_anomaly and stats["count"] > 0:
            print("  (normal)")

        # Only add to baseline history if this window wasn't itself an
        # anomaly — otherwise a real incident would poison the baseline
        # and raise the threshold for detecting the next one.
        if not latency_anomaly:
            latency_history.append(stats["avg_latency"])
        if not error_anomaly:
            error_rate_history.append(stats["error_rate"])

        print()


if __name__ == "__main__":
    if not os.environ.get("PUBSUB_EMULATOR_HOST"):
        print("PUBSUB_EMULATOR_HOST is not set — this will try to hit real "
              "GCP instead of the emulator. Set it first:")
        print('  $env:PUBSUB_EMULATOR_HOST = "localhost:8085"')
        exit(1)

    ensure_topic_and_subscription_exist()
    run()