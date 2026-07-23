from __future__ import annotations

import base64
import hashlib
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools/h3_n2_stage2d10_g4_command_protocol_20260723_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage2d10_g4_command", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ACTIVATE = MODULE.ACTIVATE_SCHEMA
VERIFY = MODULE.VERIFY_SCHEMA
CommandProtocolError = MODULE.CommandProtocolError
ActivateCommand = MODULE.ActivateCommand
VerifyCommand = MODULE.VerifyCommand
parse_command = MODULE.parse_command
redacted_summary = MODULE.redacted_summary
wifi_profile_digest = MODULE.wifi_profile_digest


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


UNLOCK_TOKEN = "11" * 32
UNLOCK_DIGEST = hashlib.sha256(bytes.fromhex(UNLOCK_TOKEN)).hexdigest()
PERSISTENCE_KEY = "22" * 32
AUTHORIZATION_DIGEST = "33" * 32
CANDIDATE_DIGEST = "44" * 32
BROKER_DIGEST = "55" * 32
ACTIVE_DIGEST = "66" * 32
SSID = b"gh-stage2d10-test"
PASSWORD = b"stage2d10-private-password"
WIFI_DIGEST = wifi_profile_digest(SSID, PASSWORD)
RUN_SUFFIX = "a1b2c3d4e5f6"


def activate_command(**overrides: str) -> str:
    values = {
        "schema": ACTIVATE,
        "run_suffix": RUN_SUFFIX,
        "unlock_token": UNLOCK_TOKEN,
        "persistence_key": PERSISTENCE_KEY,
        "authorization_digest": AUTHORIZATION_DIGEST,
        "candidate_digest": CANDIDATE_DIGEST,
        "ssid": b64(SSID),
        "password": b64(PASSWORD),
        "wifi_digest": WIFI_DIGEST,
        "broker_digest": BROKER_DIGEST,
    }
    values.update(overrides)
    return " ".join(values.values())


def verify_command(**overrides: str) -> str:
    values = {
        "schema": VERIFY,
        "run_suffix": RUN_SUFFIX,
        "unlock_token": UNLOCK_TOKEN,
        "persistence_key": PERSISTENCE_KEY,
        "active_digest": ACTIVE_DIGEST,
        "reserved": "READ_ONLY",
    }
    values.update(overrides)
    return " ".join(values.values())


class Stage2D10G4CommandProtocolTests(unittest.TestCase):
    def test_activate_valid_and_redacted(self) -> None:
        raw = activate_command()
        parsed = parse_command(raw, expected_unlock_digest=UNLOCK_DIGEST)
        self.assertIsInstance(parsed, ActivateCommand)
        self.assertEqual(parsed.run_suffix, RUN_SUFFIX)
        self.assertEqual(parsed.wifi_ssid, SSID)
        self.assertEqual(parsed.wifi_password, PASSWORD)
        self.assertEqual(parsed.raw_command_sha256, hashlib.sha256(raw.encode()).hexdigest())
        summary = redacted_summary(parsed)
        self.assertEqual(summary["execution_action"], "ACTIVATE_PROFILE")
        self.assertFalse(summary["secret_values_included"])
        rendered = repr(summary)
        self.assertNotIn(PASSWORD.decode(), rendered)
        self.assertNotIn(UNLOCK_TOKEN, rendered)
        self.assertNotIn(PERSISTENCE_KEY, rendered)

    def test_verify_valid_and_read_only(self) -> None:
        raw = verify_command()
        parsed = parse_command(raw, expected_unlock_digest=UNLOCK_DIGEST)
        self.assertIsInstance(parsed, VerifyCommand)
        summary = redacted_summary(parsed)
        self.assertTrue(summary["read_only"])
        self.assertEqual(summary["execution_action"], "VERIFY_ACTIVE_READ_ONLY")
        self.assertFalse(summary["secret_values_included"])

    def test_schema_and_field_count_fail_closed(self) -> None:
        for raw in (
            "GH2D10_PREPARE_V1 x",
            "GH2D10_CLEANUP_V1 x",
            activate_command() + " extra",
            " ".join(activate_command().split(" ")[:-1]),
            verify_command() + " extra",
            " ".join(verify_command().split(" ")[:-1]),
        ):
            with self.subTest(raw=raw.split(" ")[0]):
                with self.assertRaises(CommandProtocolError):
                    parse_command(raw)

    def test_whitespace_and_multiline_rejected(self) -> None:
        for raw in (
            " " + activate_command(),
            activate_command() + " ",
            activate_command().replace(" ", "  ", 1),
            activate_command() + "\n",
            activate_command() + "\r",
        ):
            with self.assertRaises(CommandProtocolError):
                parse_command(raw)

    def test_hex_and_run_suffix_validation(self) -> None:
        cases = (
            activate_command(run_suffix="A1B2C3D4E5F6"),
            activate_command(run_suffix="abc"),
            activate_command(unlock_token="g" * 64),
            activate_command(persistence_key="2" * 63),
            activate_command(authorization_digest="3" * 65),
            activate_command(candidate_digest="4" * 63),
            activate_command(wifi_digest="5" * 63),
            activate_command(broker_digest="6" * 65),
            verify_command(active_digest="x" * 64),
        )
        for raw in cases:
            with self.subTest(raw=raw[:40]):
                with self.assertRaises(CommandProtocolError):
                    parse_command(raw)

    def test_unlock_digest_mismatch(self) -> None:
        with self.assertRaises(CommandProtocolError):
            parse_command(activate_command(), expected_unlock_digest="77" * 32)
        with self.assertRaises(CommandProtocolError):
            parse_command(verify_command(), expected_unlock_digest="77" * 32)

    def test_wifi_base64_and_length_validation(self) -> None:
        cases = (
            activate_command(ssid="*invalid*"),
            activate_command(ssid=b64(b""), wifi_digest=wifi_profile_digest(b"", PASSWORD)),
            activate_command(
                ssid=b64(b"s" * 33),
                wifi_digest=wifi_profile_digest(b"s" * 33, PASSWORD),
            ),
            activate_command(
                password=b64(b"short"),
                wifi_digest=wifi_profile_digest(SSID, b"short"),
            ),
            activate_command(
                password=b64(b"p" * 64),
                wifi_digest=wifi_profile_digest(SSID, b"p" * 64),
            ),
        )
        for raw in cases:
            with self.subTest(raw=raw[:40]):
                with self.assertRaises(CommandProtocolError):
                    parse_command(raw)

    def test_wifi_profile_digest_binding(self) -> None:
        with self.assertRaises(CommandProtocolError):
            parse_command(activate_command(wifi_digest="88" * 32))
        changed_password = b"different-private-password"
        with self.assertRaises(CommandProtocolError):
            parse_command(
                activate_command(
                    password=b64(changed_password),
                    wifi_digest=WIFI_DIGEST,
                )
            )

    def test_verify_reserved_token_is_exact(self) -> None:
        for value in ("WRITE", "read_only", "READONLY", ""):
            with self.subTest(value=value):
                with self.assertRaises(CommandProtocolError):
                    parse_command(verify_command(reserved=value))


if __name__ == "__main__":
    unittest.main()
