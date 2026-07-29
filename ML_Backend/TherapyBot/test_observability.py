"""Focused regression tests for privacy-safe LangSmith helpers."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import observability


class ObservabilityTests(unittest.TestCase):
    def test_identifiers_are_hashed_and_stable(self):
        value = "conversation-123"
        hashed = observability.hash_identifier(value)

        self.assertEqual(hashed, observability.hash_identifier(value))
        self.assertEqual(len(hashed), 16)
        self.assertNotIn(value, hashed)

    def test_custom_span_payload_processors_remove_content(self):
        self.assertEqual(
            observability.redact_inputs({"query": "sensitive chat message"}), {}
        )
        self.assertEqual(
            observability.redact_outputs({"response": "sensitive bot reply"}), {}
        )

    def test_redaction_defaults_are_enabled(self):
        self.assertEqual(os.environ["LANGSMITH_HIDE_INPUTS"].lower(), "true")
        self.assertEqual(os.environ["LANGSMITH_HIDE_OUTPUTS"].lower(), "true")


if __name__ == "__main__":
    unittest.main()
