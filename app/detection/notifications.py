"""
Sends incident alerts to Slack via an incoming webhook.

Requires the SLACK_WEBHOOK_URL environment variable — not yet available
(pending Slack app creation, see permissions notes). Until then, calling
send_slack_alert() without it set will print a warning and skip sending,
rather than crashing — lets the rest of the pipeline keep running.
"""

import json
import os
import urllib.request
import urllib.error

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


def format_incident_message(
    service_name: str,
    anomaly_type: str,
    current_value: float,
    baseline_value: float,
    z_score: float,
    summary: str = None,
) -> dict:
    """
    Builds a Slack message payload (Block Kit format) for an incident.

    summary: optional AI-generated incident summary (from Vertex AI) —
    included when available, omitted otherwise so this works standalone
    before that piece exists.
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 Anomaly Detected: {service_name}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Type:*\n{anomaly_type}"},
                {"type": "mrkdwn", "text": f"*Z-score:*\n{z_score:.2f}"},
                {"type": "mrkdwn", "text": f"*Current:*\n{current_value:.2f}"},
                {"type": "mrkdwn", "text": f"*Baseline:*\n{baseline_value:.2f}"},
            ],
        },
    ]

    if summary:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Summary:*\n{summary}"},
            }
        )

    return {"blocks": blocks}


def send_slack_alert(
    service_name: str,
    anomaly_type: str,
    current_value: float,
    baseline_value: float,
    z_score: float,
    summary: str = None,
) -> bool:
    """Returns True if the alert was sent successfully, False otherwise."""
    if not SLACK_WEBHOOK_URL:
        print(
            "SLACK_WEBHOOK_URL not set — skipping Slack alert. "
            "(This is expected until the Slack app/webhook is created.)"
        )
        return False

    payload = format_incident_message(
        service_name, anomaly_type, current_value, baseline_value, z_score, summary
    )

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL, data=data, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                print("Slack alert sent successfully.")
                return True
            print(f"Slack alert failed: HTTP {response.status}")
            return False
    except urllib.error.URLError as e:
        print(f"Slack alert failed: {e}")
        return False


if __name__ == "__main__":
    # Manual test — set SLACK_WEBHOOK_URL first to actually send.
    send_slack_alert(
        service_name="checkout-service",
        anomaly_type="latency",
        current_value=3800.2,
        baseline_value=210.5,
        z_score=4.2,
        summary="Checkout latency spiked significantly, likely due to a "
        "downstream payment gateway timeout.",
    )
