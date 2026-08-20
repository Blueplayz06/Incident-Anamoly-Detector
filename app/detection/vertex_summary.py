"""
Generates a natural-language incident summary from anomaly data using
Vertex AI (Gemini).

NOTE: written but not yet run against live GCP — pending confirmation
it's safe to make live API calls on the jio-cloud-training project (see
team notes on the cybersecurity review). Test with USE_LIVE_VERTEX_AI=false
(default) until cleared, which uses the templated fallback instead.
"""

import os

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "jio-cloud-training")
REGION = os.environ.get("VERTEX_AI_REGION", "us-west1")  # matches the org's resourceLocations constraint

# Safety switch — defaults to the templated fallback until explicitly
# enabled. Flip to "true" only once cleared to make live GCP calls.
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
        _model = GenerativeModel("gemini-1.5-flash")
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


def _templated_fallback(service_name: str, anomaly_type: str, current_value: float,
                         baseline_value: float, z_score: float) -> str:
    """Same templated logic as the original stub — used when live Vertex AI
    is disabled or the API call fails, so the pipeline never breaks."""
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
    Same signature as the original stub — anomaly_detector.py and
    notifications.py need no changes.

    Uses live Vertex AI only when USE_LIVE_VERTEX_AI=true. Otherwise, or
    if the live call fails for any reason, falls back to a templated
    summary so the pipeline never breaks on an API error.
    """
    if not USE_LIVE_VERTEX_AI:
        return _templated_fallback(
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
        print(f"Vertex AI call failed, using templated fallback: {e}")
        return _templated_fallback(
            service_name, anomaly_type, current_value, baseline_value, z_score
        )
