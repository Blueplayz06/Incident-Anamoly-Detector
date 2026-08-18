"""
Unit tests for validate_log — no GCP/emulator needed, pure logic tests.
Run with: python -m pytest test_main.py
"""

from main import validate_log

VALID_LOG = {
    "timestamp": "2026-08-19T09:32:11.204Z",
    "request_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "service_name": "checkout-service",
    "endpoint": "/api/checkout",
    "method": "POST",
    "status_code": 200,
    "log_level": "INFO",
    "latency_ms": 120.5,
    "message": "Order placed successfully",
}


def test_valid_log_passes():
    is_valid, reason = validate_log(VALID_LOG)
    assert is_valid
    assert reason == ""


def test_missing_required_field_fails():
    bad_log = VALID_LOG.copy()
    del bad_log["latency_ms"]
    is_valid, reason = validate_log(bad_log)
    assert not is_valid
    assert "latency_ms" in reason


def test_wrong_type_status_code_fails():
    bad_log = VALID_LOG.copy()
    bad_log["status_code"] = "200"  # string instead of int
    is_valid, reason = validate_log(bad_log)
    assert not is_valid
    assert "status_code" in reason


def test_invalid_log_level_fails():
    bad_log = VALID_LOG.copy()
    bad_log["log_level"] = "DEBUG"  # not in INFO/WARN/ERROR
    is_valid, reason = validate_log(bad_log)
    assert not is_valid
    assert "log_level" in reason


def test_optional_fields_can_be_missing():
    # user_id and error_type are optional per docs/schema.md
    log = VALID_LOG.copy()
    is_valid, reason = validate_log(log)
    assert is_valid
