from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from h3_n2_stage2d9_prepare_command_protocol_20260722_v1 import (  # noqa: E402
    CommandError,
    SCHEMA,
    VERIFY_SCHEMA,
    build_candidate,
    candidate_digest,
    parse_command,
    render_command,
)


class CommandProtocolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.unlock = bytes(range(32)).hex()
        self.unlock_digest = hashlib.sha256(bytes.fromhex(self.unlock)).hexdigest()
        self.key = bytes(range(32, 64)).hex()
        self.auth = hashlib.sha256(b"authorization").hexdigest()
        self.line = render_command(
            SCHEMA,
            "abcd1234",
            self.unlock,
            self.key,
            self.auth,
        )

    def test_prepare_round_trip(self) -> None:
        parsed = parse_command(self.line, self.unlock_digest)
        self.assertEqual(parsed.schema, SCHEMA)
        self.assertEqual(parsed.run_suffix, "abcd1234")
        self.assertEqual(
            parsed.candidate_digest,
            candidate_digest(build_candidate("abcd1234", self.auth)),
        )

    def test_verify_round_trip(self) -> None:
        line = render_command(
            VERIFY_SCHEMA,
            "abcd1234",
            self.unlock,
            self.key,
            self.auth,
        )
        parsed = parse_command(
            line,
            self.unlock_digest,
            expected_schema=VERIFY_SCHEMA,
        )
        self.assertEqual(parsed.schema, VERIFY_SCHEMA)

    def test_wrong_unlock_fails(self) -> None:
        with self.assertRaisesRegex(CommandError, "unlock digest"):
            parse_command(self.line, "f" * 64)

    def test_candidate_digest_mismatch_fails(self) -> None:
        parts = self.line.split(" ")
        parts[-1] = "f" * 64
        with self.assertRaisesRegex(CommandError, "candidate digest"):
            parse_command(" ".join(parts), self.unlock_digest)

    def test_zero_secrets_fail(self) -> None:
        for index in (2, 3, 4):
            parts = self.line.split(" ")
            parts[index] = "0" * 64
            with self.assertRaisesRegex(CommandError, "zero secret"):
                parse_command(" ".join(parts), self.unlock_digest)

    def test_malformed_shapes_fail(self) -> None:
        for line in (
            "",
            SCHEMA,
            self.line + " extra",
            self.line.replace(" ", "  ", 1),
        ):
            with self.assertRaises(CommandError):
                parse_command(line, self.unlock_digest)

    def test_suffix_is_restricted(self) -> None:
        parts = self.line.split(" ")
        parts[1] = "../bad"
        with self.assertRaisesRegex(CommandError, "suffix"):
            parse_command(" ".join(parts), self.unlock_digest)

    def test_prepare_and_verify_schema_cannot_be_substituted(self) -> None:
        verify_line = render_command(
            VERIFY_SCHEMA,
            "abcd1234",
            self.unlock,
            self.key,
            self.auth,
        )
        with self.assertRaisesRegex(CommandError, "shape"):
            parse_command(verify_line, self.unlock_digest, expected_schema=SCHEMA)

    def test_candidate_contains_only_isolated_test_identifiers(self) -> None:
        candidate = build_candidate("abcd1234", self.auth)
        self.assertEqual(candidate["credential_generation"], 1)
        self.assertEqual(candidate["broker_host"], "stage2d9.invalid")
        self.assertTrue(str(candidate["test_run_id"]).startswith("gh-test-"))
        self.assertTrue(str(candidate["mqtt_client_id"]).startswith("gh-test-"))
        self.assertTrue(str(candidate["test_topic_root"]).startswith("gh-test/"))
        self.assertNotIn("homeassistant", str(candidate["test_topic_root"]))
        self.assertNotIn("gh/v1/", str(candidate["test_topic_root"]))


if __name__ == "__main__":
    unittest.main()
