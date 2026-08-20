"""
Continuously sends requests to the sample app to simulate ongoing traffic.
Run this alongside the app (uvicorn) to generate a steady stream of logs.

Run:
    python traffic_generator.py
"""

import random
import time

import requests

BASE_URL = "http://localhost:8000"

ENDPOINTS = [
    ("POST", "/api/cart/add"),
    ("POST", "/api/checkout"),
    ("GET", "/api/browse"),
]

# Weighted so browsing happens most often, checkout least often —
# roughly mimics real e-commerce traffic shape.
WEIGHTS = [0.3, 0.15, 0.55]


def send_request():
    method, path = random.choices(ENDPOINTS, weights=WEIGHTS, k=1)[0]
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            requests.get(url, timeout=5)
        else:
            requests.post(url, timeout=5)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    print(f"Sending traffic to {BASE_URL} — Ctrl+C to stop")
    print("Tip: trigger a demo spike anytime with:")
    print(f"  curl -X POST {BASE_URL}/admin/trigger-error-burst")
    print(f"  curl -X POST {BASE_URL}/admin/stop-error-burst")
    print()

    while True:
        send_request()
        time.sleep(random.uniform(0.1, 0.5))  # roughly 2-10 requests/sec
