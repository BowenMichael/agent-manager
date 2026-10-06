"""
Unit tests for Sentry Exception Ingestion & Autonomous Bug Reproduction Service.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import unittest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from agent_manager.services.sentry_service import (
    compute_error_signature,
    is_duplicate_sentry_event,
    parse_sentry_payload,
    format_sentry_issue_body,
    format_reproduction_prompt,
    SentryErrorDetails,
    SentryFrame
)
from agent_manager.api.routes.webhooks_sentry import router as sentry_router


class TestSentryService(unittest.TestCase):
    """Test suite for Sentry payload parsing, deduplication, and prompt formatting."""

    def test_compute_error_signature_deterministic(self):
        """Verify MD5 error signature is deterministic and identical for same parameters."""
        sig1 = compute_error_signature("TypeError", "user_service.py:42", "NoneType has no attribute 'id'")
        sig2 = compute_error_signature("TypeError", "user_service.py:42", "NoneType has no attribute 'id'")
        sig3 = compute_error_signature("ValueError", "user_service.py:42", "NoneType has no attribute 'id'")
        self.assertEqual(sig1, sig2)
        self.assertNotEqual(sig1, sig3)
        self.assertEqual(len(sig1), 32)

    def test_duplicate_event_suppression(self):
        """Verify duplicate events are detected and flagged."""
        sig = "test_unique_signature_123"
        self.assertFalse(is_duplicate_sentry_event(sig))
        self.assertTrue(is_duplicate_sentry_event(sig))

    def test_parse_sentry_payload(self):
        """Verify standard Sentry webhook payload is parsed into structured error details."""
        sample_payload = {
            "id": "evt_12345",
            "project_name": "agent-manager",
            "event": {
                "event_id": "evt_12345",
                "culprit": "agent_manager.auth.jwt_service:32",
                "environment": "production",
                "exception": {
                    "values": [
                        {
                            "type": "KeyError",
                            "value": "'sub' is missing from JWT payload",
                            "stacktrace": {
                                "frames": [
                                    {
                                        "filename": "agent_manager/auth/jwt_service.py",
                                        "function": "verify_auth_token",
                                        "lineno": 32,
                                        "context_line": "return payload['sub']"
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
        error = parse_sentry_payload(sample_payload)
        self.assertEqual(error.event_id, "evt_12345")
        self.assertEqual(error.error_type, "KeyError")
        self.assertEqual(error.error_value, "'sub' is missing from JWT payload")
        self.assertEqual(error.culprit, "agent_manager.auth.jwt_service:32")
        self.assertEqual(len(error.stacktrace_frames), 1)
        self.assertEqual(error.stacktrace_frames[0].lineno, 32)

    def test_format_sentry_issue_body(self):
        """Verify generated GitHub issue body contains stack trace and reproduction criteria."""
        error = SentryErrorDetails(
            event_id="evt_test",
            project="fitelo",
            culprit="score_calculator.py:15",
            error_type="ZeroDivisionError",
            error_value="division by zero in rank calculation",
            stacktrace_frames=[
                SentryFrame(filename="score_calculator.py", function="calc_rank", lineno=15, context_line="return total / count")
            ]
        )
        body = format_sentry_issue_body(error)
        self.assertIn("🚨 Production Exception: `ZeroDivisionError`", body)
        self.assertIn("score_calculator.py:15", body)
        self.assertIn("Replicate the exception in an isolated unit or integration test.", body)

    def test_format_reproduction_prompt(self):
        """Verify prompt generated for autonomous agent provides clear reproduction directives."""
        error = SentryErrorDetails(
            event_id="evt_test",
            project="agent-manager",
            culprit="poller.py:50",
            error_type="ConnectionError",
            error_value="GitHub API rate limit exceeded"
        )
        prompt = format_reproduction_prompt(error, issue_number=97)
        self.assertIn("Issue #97", prompt)
        self.assertIn("ConnectionError", prompt)
        self.assertIn("Write an isolated reproduction test", prompt)


class TestSentryWebhookEndpoint(unittest.TestCase):
    """Test suite for /api/webhooks/sentry endpoint."""

    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(sentry_router)
        self.client = TestClient(self.app)

    def test_sentry_webhook_ingestion(self):
        """Verify Sentry webhook accepts error payload and creates healing task."""
        payload = {
            "id": "evt_webhook_test_1",
            "project_name": "agent-manager",
            "event": {
                "event_id": "evt_webhook_test_1",
                "culprit": "webhooks.py:99",
                "exception": {
                    "values": [{"type": "ValueError", "value": "invalid signature header"}]
                }
            }
        }
        res = self.client.post("/api/webhooks/sentry", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ingested")
        self.assertTrue(data["issue_created"])
        self.assertFalse(data["duplicate"])

    def test_sentry_webhook_duplicate_ignored(self):
        """Verify second delivery of the exact same event signature is ignored."""
        payload = {
            "id": "evt_webhook_test_2",
            "project_name": "agent-manager",
            "event": {
                "event_id": "evt_webhook_test_2",
                "culprit": "unique_culprit.py:10",
                "exception": {
                    "values": [{"type": "UniqueError", "value": "duplicate trigger test"}]
                }
            }
        }
        res1 = self.client.post("/api/webhooks/sentry", json=payload)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["status"], "ingested")

        res2 = self.client.post("/api/webhooks/sentry", json=payload)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["status"], "ignored_duplicate")
        self.assertTrue(res2.json()["duplicate"])


if __name__ == "__main__":
    unittest.main()
