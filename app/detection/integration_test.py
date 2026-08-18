"""
Local integration test — publishes a real log message to the Pub/Sub
emulator, pulls it back, and runs it through process_log_message exactly
as Cloud Functions would deliver it (base64-encoded event data).

BigQuery writes are mocked here since there's no local BigQuery emulator —
this test verifies the Pub/Sub message handling and validation path work
correctly end-to-end, not the actual BigQuery insert.

Prerequisites:
    docker compose up -d pubsub-emulator      (run from repo root)

Run:
    $env:PUBSUB_EMULATOR_HOST = "localhost:8085"
    $env:GOOGLE_CLOUD_PROJECT = "local-dev-project"
    python integration_test.py
"""

import base64
import json
import os
import time
from unittest.mock import patch

from google.cloud import pubsub_v1

import main as ingestion_main

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "local-dev-project")
TOPIC_ID = "log-ingestion-topic"
SUBSCRIPTION_ID = "log-ingestion-sub"

TEST_MESSAGE = {
    "timestamp": "2026-08-19T10:15:00.000Z",
    "request_id": "test-req-001",
    "service_name": "checkout-service",
    "endpoint": "/api/checkout",
    "method": "POST",
    "status_code": 500,
    "log_level": "ERROR",
    "latency_ms": 3800.2,
    "message": "Payment gateway timeout",
    "error_type": "TimeoutError",
}


def setup_topic_and_subscription():
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
    sub_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    try:
        publisher.create_topic(request={"name": topic_path})
        print(f"Created topic: {topic_path}")
    except Exception:
        print("Topic already exists, continuing.")

    try:
        subscriber.create_subscription(
            request={"name": sub_path, "topic": topic_path}
        )
        print(f"Created subscription: {sub_path}")
    except Exception:
        print("Subscription already exists, continuing.")

    return publisher, subscriber, topic_path, sub_path


def publish_test_message(publisher, topic_path):
    data = json.dumps(TEST_MESSAGE).encode("utf-8")
    future = publisher.publish(topic_path, data)
    message_id = future.result()
    print(f"Published message ID: {message_id}")


def pull_and_process(subscriber, sub_path):
    response = subscriber.pull(
        request={"subscription": sub_path, "max_messages": 1}, timeout=10
    )

    if not response.received_messages:
        print("No messages received — check the emulator is running and the "
              "message was published successfully.")
        return

    received = response.received_messages[0]

    # Reconstruct the event exactly as Cloud Functions/Pub/Sub trigger
    # would deliver it — base64-encoded data field.
    event = {
        "data": base64.b64encode(received.message.data).decode("utf-8")
    }

    print(f"Pulled message, running through process_log_message...")

    # Mock the BigQuery write since there's no local BigQuery emulator —
    # this confirms the message parses and validates correctly, which is
    # what this test is actually checking.
    with patch.object(ingestion_main, "write_to_bigquery") as mock_write:
        ingestion_main.process_log_message(event, context=None)

        if mock_write.called:
            table_id, rows = mock_write.call_args[0]
            print(f"\n✅ write_to_bigquery called with table='{table_id}'")
            print(f"   Row data: {rows}")
        else:
            print("\n❌ write_to_bigquery was never called — check for an "
                  "exception above.")

    subscriber.acknowledge(
        request={"subscription": sub_path, "ack_ids": [received.ack_id]}
    )


if __name__ == "__main__":
    if not os.environ.get("PUBSUB_EMULATOR_HOST"):
        print("PUBSUB_EMULATOR_HOST is not set — this will try to hit real "
              "GCP instead of the emulator. Set it first:")
        print('  $env:PUBSUB_EMULATOR_HOST = "localhost:8085"')
        exit(1)

    publisher, subscriber, topic_path, sub_path = setup_topic_and_subscription()
    publish_test_message(publisher, topic_path)
    time.sleep(1)  # give the emulator a moment
    pull_and_process(subscriber, sub_path)
