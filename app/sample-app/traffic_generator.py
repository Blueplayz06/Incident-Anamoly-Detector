"""
Continuously sends requests to the sample app to simulate ongoing traffic.
Run this alongside the app (uvicorn locally, or the real Cloud Run URL)
to generate a steady stream of logs.

For local dev (default): just run it, no extra setup.

For the real deployed Cloud Run app (which requires authentication, since
this org's policy blocks public --allow-unauthenticated access):
    export TARGET_BASE_URL="https://sample-app-868369668937.us-west1.run.app"
    python3 traffic_generator.py

Run:
    python traffic_generator.py
"""

import os
import random
import subprocess
import time

import requests

BASE_URL = os.environ.get("TARGET_BASE_URL", "http://localhost:8000")
IS_REMOTE = BASE_URL != "http://localhost:8000"

ENDPOINTS = [
    ("POST", "/api/cart/add"),
    ("POST", "/api/checkout"),
    ("GET", "/api/browse"),
]

# Weighted so browsing happens most often, checkout least often —
# roughly mimics real e-commerce traffic shape.
WEIGHTS = [0.3, 0.15, 0.55]


def get_auth_headers() -> dict:
    """Only needed when hitting the real Cloud Run URL, which requires
    authentication under this org's security policy (public access is
    blocked). Fetches a fresh identity token via gcloud, scoped to this
    specific service's audience — an unscoped token gets rejected with
    401 even though it looks superficially valid."""
    if not IS_REMOTE:
        return {}
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-identity-token", f"--audiences={BASE_URL}"],
            text=True,
        ).strip()
        return {"Authorization": f"Bearer {token}"}
    except subprocess.CalledProcessError as e:
        print(f"Failed to get identity token: {e}")
        return {}


def send_request(headers: dict):
    method, path = random.choices(ENDPOINTS, weights=WEIGHTS, k=1)[0]
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            requests.get(url, headers=headers, timeout=5)
        else:
            requests.post(url, headers=headers, timeout=5)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    print(f"Sending traffic to {BASE_URL} — Ctrl+C to stop")
    if IS_REMOTE:
        print("(Using authenticated requests — remote Cloud Run target)")
    print("Tip: trigger a demo spike anytime with:")
    print(f"  curl -X POST {BASE_URL}/admin/trigger-error-burst")
    print(f"  curl -X POST {BASE_URL}/admin/stop-error-burst")
    print()

    # Fetch the auth token once up front, not on every single request —
    # identity tokens are valid for about an hour, refreshing per-request
    # would be wasteful and slow.
    headers = get_auth_headers()
    token_fetched_at = time.time()

    while True:
        # Refresh the token every ~45 min to stay safely within its lifetime.
        if IS_REMOTE and time.time() - token_fetched_at > 2700:
            headers = get_auth_headers()
            token_fetched_at = time.time()

        send_request(headers)
        time.sleep(random.uniform(0.1, 0.5))  # roughly 2-10 requests/sec