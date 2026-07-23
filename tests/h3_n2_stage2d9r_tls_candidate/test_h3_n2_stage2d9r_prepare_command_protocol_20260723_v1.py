#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_prepare_command_protocol_20260723_v1.py"
spec = importlib.util.spec_from_file_location("stage2d9r_command", TOOL)
assert spec is not None and spec.loader is not None
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)

VALID_CA_PEM = (
    "-----BEGIN CERTIFICATE-----\n"
    + ("QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFB\n" * 6)
    + "-----END CERTIFICATE-----\n"
)
UNLOCK = "1" * 64
KEY = "2" * 64
AUTH = "3" * 64
SUFFIX = "tlsvalid01"
UNLOCK_DIGEST = protocol.sha256_hex(bytes.fromhex(UNLOCK))


class Stage2D9RPrepareCommandProtocolTest(unittest.TestCase):
    def prepare(self) -> str:
        return protocol.render_prepare(SUFFIX, UNLOCK, KEY, AUTH, VALID_CA_PEM)

    def test_prepare_round_trip(self) -> None:
        line = self.prepare()
        parsed = protocol.parse_prepare(line, UNLOCK_DIGEST)
        expected = protocol.build_candidate(SUFFIX, AUTH, VALID_CA_PEM)
        self.assertEqual(parsed.run_suffix, SUFFIX)
        self.assertEqual(parsed.ca_pem, VALID_CA_PEM)
        self.assertEqual(parsed.ca_pem_sha256, protocol.sha256_hex(VALID_CA_PEM.encode("ascii")))
        self.assertEqual(parsed.candidate_digest, protocol.candidate_digest(expected))

    def test_verify_round_trip_without_ca_replay(self) -> None:
        digest = protocol.candidate_digest(
            protocol.build_candidate(SUFFIX, AUTH, VALID_CA_PEM)
        )
        line = protocol.render_verify(SUFFIX, UNLOCK, KEY, digest)
        parsed = protocol.parse_verify(line, UNLOCK_DIGEST)
        self.assertEqual(parsed.candidate_digest, digest)
        self.assertNotIn("BEGIN CERTIFICATE", line)
        self.assertNotIn(AUTH, line)

    def test_candidate_uses_tls_valid_replacement_identity(self) -> None:
        candidate = protocol.build_candidate(SUFFIX, AUTH, VALID_CA_PEM)
        self.assertEqual(candidate["broker_host"], "stage2d9r.local")
        self.assertEqual(candidate["broker_tls_server_name"], "stage2d9r.local")
        self.assertEqual(candidate["ca_pem"], VALID_CA_PEM)
        self.assertNotEqual(candidate["ca_pem"], "stage2d9-test-ca")

    def test_unlock_digest_is_bound(self) -> None:
        with self.assertRaisesRegex(protocol.CommandError, "unlock digest mismatch"):
            protocol.parse_prepare(self.prepare(), "4" * 64)

    def test_ca_digest_is_bound(self) -> None:
        parts = self.prepare().split(" ")
        parts[6] = "4" * 64
        with self.assertRaisesRegex(protocol.CommandError, "CA PEM digest mismatch"):
            protocol.parse_prepare(" ".join(parts), UNLOCK_DIGEST)

    def test_candidate_digest_is_bound(self) -> None:
        parts = self.prepare().split(" ")
        parts[7] = "5" * 64
        with self.assertRaisesRegex(protocol.CommandError, "candidate digest mismatch"):
            protocol.parse_prepare(" ".join(parts), UNLOCK_DIGEST)

    def test_ca_framing_is_exact(self) -> None:
        for ca in (
            VALID_CA_PEM.replace("BEGIN CERTIFICATE", "BEGIN X509 CERTIFICATE"),
            VALID_CA_PEM.rstrip("\n"),
            VALID_CA_PEM.replace("\n", "\r\n"),
        ):
            with self.assertRaises(protocol.CommandError):
                protocol.render_prepare(SUFFIX, UNLOCK, KEY, AUTH, ca)

    def test_ca_length_is_bounded(self) -> None:
        for ca in (
            "-----BEGIN CERTIFICATE-----\nQQ==\n-----END CERTIFICATE-----\n",
            "-----BEGIN CERTIFICATE-----\n" + ("A" * 64 + "\n") * 80 + "-----END CERTIFICATE-----\n",
        ):
            with self.assertRaisesRegex(protocol.CommandError, "CA PEM length invalid"):
                protocol.render_prepare(SUFFIX, UNLOCK, KEY, AUTH, ca)

    def test_prepare_and_verify_schemas_are_not_interchangeable(self) -> None:
        digest = protocol.candidate_digest(
            protocol.build_candidate(SUFFIX, AUTH, VALID_CA_PEM)
        )
        verify = protocol.render_verify(SUFFIX, UNLOCK, KEY, digest)
        with self.assertRaisesRegex(protocol.CommandError, "PREPARE command shape invalid"):
            protocol.parse_prepare(verify, UNLOCK_DIGEST)
        with self.assertRaisesRegex(protocol.CommandError, "VERIFY command shape invalid"):
            protocol.parse_verify(self.prepare(), UNLOCK_DIGEST)

    def test_zero_secrets_are_rejected(self) -> None:
        for index, message in (
            (2, "zero unlock token rejected"),
            (3, "zero persistence key rejected"),
            (4, "zero authorization digest rejected"),
        ):
            parts = self.prepare().split(" ")
            parts[index] = "0" * 64
            with self.assertRaisesRegex(protocol.CommandError, message):
                protocol.parse_prepare(" ".join(parts), UNLOCK_DIGEST)

    def test_whitespace_and_line_endings_fail_closed(self) -> None:
        valid = self.prepare()
        for line in (
            " " + valid,
            valid + " ",
            valid.replace(" ", "  ", 1),
            valid + "\nextra",
        ):
            with self.assertRaises(protocol.CommandError):
                protocol.parse_prepare(line, UNLOCK_DIGEST)


if __name__ == "__main__":
    unittest.main()
