"""
Generates a natural-language incident summary from anomaly data.

*** PLACEHOLDER — NOT REAL VERTEX AI ***
This is a templated, rule-based stub, not an actual Vertex AI call. It
exists so the rest of the pipeline (detection → summary → alert) can be
built and tested end-to-end without needing real GCP/Vertex AI access.

Person B: replace generate_incident_summary()'s body with an actual
Vertex AI prompt + API call. Keep the same function signature so nothing
downstream (notifications.py, anomaly_detector.py) needs to change —
just swap what happens inside this one function.
"""


def generate_incident_summary(
    service_name: str,
    anomaly_type: str,
    current_value: float,
    baseline_value: float,
    z_score: float,
) -> str:
    """
    *** STUB — replace with real Vertex AI prompt + call ***

    A real version would send something like:
        "An anomaly was detected in {service_name}. {anomaly_type} is
        currently {current_value}, compared to a baseline of
        {baseline_value} (z-score: {z_score}). Write a 2-3 sentence
        incident summary a site reliability engineer could read to
        quickly understand what's happening and likely next steps."
    to Vertex AI, and return its response.

    For now, returns a templated summary using the same inputs, so the
    rest of the pipeline has something realistic to work with.
    """
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
