"""
Sample e-commerce app — generates realistic request logs matching
docs/schema.md, with built-in random errors/latency spikes to give the
anomaly detection something to detect.

Each request publishes a log line directly to the Pub/Sub topic
(log-ingestion-topic), same as it would in the real pipeline — just
pointed at the local emulator during development.
"""

import json
import random
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from google.cloud import pubsub_v1
import os

app = FastAPI(title="Sample E-Commerce App")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "local-dev-project")
TOPIC_ID = "log-ingestion-topic"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

# Global flag to force a burst of errors on demand — for demo purposes.
FORCE_ERROR_BURST = {"active": False}


def publish_log(service_name: str, endpoint: str, method: str,
                 status_code: int, latency_ms: float, message: str,
                 error_type: str = None, user_id: str = None):
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": str(uuid.uuid4()),
        "service_name": service_name,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "log_level": "ERROR" if status_code >= 500 else (
            "WARN" if status_code >= 400 else "INFO"
        ),
        "latency_ms": round(latency_ms, 2),
        "message": message,
    }
    if error_type:
        log_entry["error_type"] = error_type
    if user_id:
        log_entry["user_id"] = user_id

    data = json.dumps(log_entry).encode("utf-8")
    publisher.publish(topic_path, data)
    return log_entry


def simulate_latency(base_ms: float, spike_chance: float = 0.05) -> float:
    """Normal latency most of the time, occasional spike."""
    if random.random() < spike_chance or FORCE_ERROR_BURST["active"]:
        return base_ms * random.uniform(8, 20)  # spike
    return base_ms * random.uniform(0.7, 1.5)


def should_error(base_error_rate: float = 0.03) -> bool:
    """Normal low error rate, forced high during a burst."""
    if FORCE_ERROR_BURST["active"]:
        return random.random() < 0.6
    return random.random() < base_error_rate


@app.post("/api/cart/add")
def add_to_cart():
    latency = simulate_latency(base_ms=80)
    time.sleep(latency / 1000)

    if should_error():
        log = publish_log(
            service_name="cart-service",
            endpoint="/api/cart/add",
            method="POST",
            status_code=500,
            latency_ms=latency,
            message="Failed to add item to cart",
            error_type="CartServiceError",
            user_id=f"user_{random.randint(1000, 9999)}",
        )
        raise HTTPException(status_code=500, detail=log)

    log = publish_log(
        service_name="cart-service",
        endpoint="/api/cart/add",
        method="POST",
        status_code=200,
        latency_ms=latency,
        message="Item added to cart",
        user_id=f"user_{random.randint(1000, 9999)}",
    )
    return log


@app.post("/api/checkout")
def checkout():
    latency = simulate_latency(base_ms=200)
    time.sleep(latency / 1000)

    if should_error():
        log = publish_log(
            service_name="checkout-service",
            endpoint="/api/checkout",
            method="POST",
            status_code=500,
            latency_ms=latency,
            message="Payment gateway timeout",
            error_type="TimeoutError",
            user_id=f"user_{random.randint(1000, 9999)}",
        )
        raise HTTPException(status_code=500, detail=log)

    log = publish_log(
        service_name="checkout-service",
        endpoint="/api/checkout",
        method="POST",
        status_code=200,
        latency_ms=latency,
        message="Order placed successfully",
        user_id=f"user_{random.randint(1000, 9999)}",
    )
    return log


@app.get("/api/browse")
def browse():
    latency = simulate_latency(base_ms=50)
    time.sleep(latency / 1000)

    if should_error():
        log = publish_log(
            service_name="browse-service",
            endpoint="/api/browse",
            method="GET",
            status_code=404,
            latency_ms=latency,
            message="Product not found",
            error_type="NotFoundError",
        )
        raise HTTPException(status_code=404, detail=log)

    log = publish_log(
        service_name="browse-service",
        endpoint="/api/browse",
        method="GET",
        status_code=200,
        latency_ms=latency,
        message="Products retrieved",
    )
    return log


@app.post("/admin/trigger-error-burst")
def trigger_error_burst():
    """Manually trigger a burst of errors/latency spikes for demo purposes."""
    FORCE_ERROR_BURST["active"] = True
    return {"status": "error burst activated"}


@app.post("/admin/stop-error-burst")
def stop_error_burst():
    FORCE_ERROR_BURST["active"] = False
    return {"status": "error burst deactivated"}


@app.get("/health")
def health():
    return {"status": "ok"}
