"""
Generates a natural-language incident summary from anomaly data.

Primary path: a deterministic, rule-based summary generator (no external
dependency, no API cost, works identically every time). This is the
default and the design this project ships with.

Optional enhancement: a real Vertex AI (Gemini) call can be enabled via
USE_LIVE_VERTEX_AI=true. As of testing on 2026-09-02, this project's
GCP setup does not have full generative-model API access enabled, and
model availability/naming for Gemini also changes over time — so this
path is best-effort and not currently verified working. If it's ever
enabled and the call fails for any reason, this module automatically
falls back to the rule-based generator, so the pipeline never breaks.
"""

import os

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "jio-cloud-training")
REGION = os.environ.get("VERTEX_AI_REGION", "us-west1")  # matches the org's resourceLocations constraint

# Off by default. This project's rule-based generator is the primary,
# supported path — see module docstring. Only enable this once Vertex AI
# generative-model access is confirmed working for this project.
USE_LIVE_VERTEX_AI = os.environ.get("USE_LIVE_VERTEX_AI", "false").lower() == "true"

_model = None


def _get_model():
    """Lazily initializes the Vertex AI client — keeps this importable
    without live GCP credentials when USE_LIVE_VERTEX_AI is false."""
    global _model
    if _model is None:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=PROJECT_ID, location=REGION)
        _model = GenerativeModel("gemini-1.5-flash")  # TESTING: try alternate model names if this 404s
    return _model


def _build_prompt(service_name: str, anomaly_type: str, current_value: float,
                   baseline_value: float, z_score: float) -> str:
    return (
        f"An anomaly was detected in an application's {anomaly_type} metric.\n\n"
        f"Service: {service_name}\n"
        f"Anomaly type: {anomaly_type}\n"
        f"Current value: {current_value:.2f}\n"
        f"Normal baseline: {baseline_value:.2f}\n"
        f"Z-score: {z_score:.2f}\n\n"
        f"Write a 2-3 sentence incident summary that a site reliability "
        f"engineer could quickly read to understand what's happening and "
        f"what to check next. Be concise and specific — no filler."
    )


def _rule_based_summary(service_name: str, anomaly_type: str, current_value: float,
                         baseline_value: float, z_score: float) -> str:
    """The primary summary generator for this project — deterministic,
    no external dependency. Used directly by default, and also used as
    the automatic fallback if a live Vertex AI call is enabled but fails."""
    if anomaly_type == "latency":
        severity = "significant" if z_score > 5 else "moderate"
        return (
            f"{service_name} is experiencing a {severity} latency spike. "
            f"Current average latency is {current_value:.0f}ms, "
            f"compared to a normal baseline of {baseline_value:.0f}ms "
            f"(z-score: {z_score:.1f}). This may indicate a downstream "
            f"dependency slowdown or resource contention. Recommend "
            f"checking {service_name}'s dependent services and recent "
            f"deploys."
        )

    if anomaly_type == "error_rate":
        severity = "significant" if z_score > 5 else "moderate"
        return (
            f"{service_name} is experiencing a {severity} increase in "
            f"error rate. Current error rate is {current_value:.1%}, "
            f"compared to a normal baseline of {baseline_value:.1%} "
            f"(z-score: {z_score:.1f}). Recommend checking recent "
            f"deploys, dependency health, and application logs for "
            f"{service_name}."
        )

    return (
        f"An anomaly was detected in {service_name} ({anomaly_type}). "
        f"Current value: {current_value:.2f}, baseline: {baseline_value:.2f}, "
        f"z-score: {z_score:.2f}."
    )


def generate_incident_summary(
    service_name: str,
    anomaly_type: str,
    current_value: float,
    baseline_value: float,
    z_score: float,
) -> str:
    """
    Same signature regardless of which path generates the summary —
    anomaly_detector.py and notifications.py need no changes either way.

    Uses the rule-based generator by default. If USE_LIVE_VERTEX_AI=true,
    attempts a real Vertex AI call first and falls back to the rule-based
    generator automatically if that call fails for any reason.
    """
    if not USE_LIVE_VERTEX_AI:
        return _rule_based_summary(
            service_name, anomaly_type, current_value, baseline_value, z_score
        )

    try:
        model = _get_model()
        prompt = _build_prompt(
            service_name, anomaly_type, current_value, baseline_value, z_score
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Vertex AI call failed, using rule-based generator: {e}")
        return _rule_based_summary(
            service_name, anomaly_type, current_value, baseline_value, z_score
        )
