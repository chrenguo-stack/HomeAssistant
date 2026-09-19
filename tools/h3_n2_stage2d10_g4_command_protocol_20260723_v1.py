#!/usr/bin/env python3
"""Strict private serial command parser for Stage 2D-10 G4.

The module parses private command material but never emits it. Public callers
should retain only command SHA-256 values and redacted booleans.
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import hmac
import re
from typing import Literal

ACTIVATE_SCHEMA = "GH2D10_ACTIVATE_V1"
VERIFY_SCHEMA = "GH2D10_VERIFY_ACTIVE_V1"
RUN_SUFFIX_RE = re.compile(r"^[0-9a-f]{12}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class CommandProtocolError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class ActivateCommand:
    schema: Literal["GH2D10_ACTIVATE_V1"]
    run_suffix: str
    unlock_token_hex: str
    persistence_key_hex: str
    authorization_digest: str
    candidate_digest: str
    wifi_ssid: bytes
    wifi_password: bytes
    wifi_profile_digest: str
    broker_configuration_digest: str
    raw_command_sha256: str


@dataclasses.dataclass(frozen=True)
class VerifyCommand:
    schema: Literal["GH2D10_VERIFY_ACTIVE_V1"]
    run_suffix: str
    unlock_token_hex: str
    persistence_key_hex: str
    active_digest: str
    raw_command_sha256: str


ParsedCommand = ActivateCommand | VerifyCommand


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CommandProtocolError(message)


def _hex64(value: str, field: str) -> str:
    _require(HEX64_RE.fullmatch(value) is not None, f"{field} invalid")
    return value


def _run_suffix(value: str) -> str:
    _require(RUN_SUFFIX_RE.fullmatch(value) is not None, "run suffix invalid")
    return value


def _decode_base64url(value: str, field: str) -> bytes:
    _require(BASE64URL_RE.fullmatch(value) is not None, f"{field} invalid")
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise CommandProtocolError(f"{field} invalid") from exc
    canonical = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
    _require(canonical == value, f"{field} is not canonical base64url")
    return decoded


def wifi_profile_digest(ssid: bytes, password: bytes) -> str:
    payload = b"gh.stage2d10.wifi/1\x00" + ssid + b"\x00" + password
    return hashlib.sha256(payload).hexdigest()


def command_sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_command(
    raw: str,
    *,
    expected_unlock_digest: str | None = None,
) -> ParsedCommand:
    _require("\n" not in raw and "\r" not in raw, "multiline command forbidden")
    _require(raw == raw.strip(), "leading or trailing whitespace forbidden")
    _require("  " not in raw, "repeated whitespace forbidden")
    fields = raw.split(" ")
    _require(fields and fields[0] in {ACTIVATE_SCHEMA, VERIFY_SCHEMA}, "schema invalid")

    unlock_digest = None
    if expected_unlock_digest is not None:
        unlock_digest = _hex64(expected_unlock_digest, "expected unlock digest")

    if fields[0] == ACTIVATE_SCHEMA:
        _require(len(fields) == 10, "ACTIVATE field count invalid")
        (
            schema,
            run_suffix,
            unlock_token,
            persistence_key,
            authorization_digest,
            candidate_digest,
            ssid_b64,
            password_b64,
            wifi_digest,
            broker_digest,
        ) = fields
        _run_suffix(run_suffix)
        _hex64(unlock_token, "unlock token")
        _hex64(persistence_key, "persistence key")
        _hex64(authorization_digest, "authorization digest")
        _hex64(candidate_digest, "candidate digest")
        _hex64(wifi_digest, "wifi profile digest")
        _hex64(broker_digest, "broker configuration digest")
        ssid = _decode_base64url(ssid_b64, "wifi ssid")
        password = _decode_base64url(password_b64, "wifi password")
        _require(1 <= len(ssid) <= 32, "wifi ssid length invalid")
        _require(8 <= len(password) <= 63, "wifi password length invalid")
        _require(b"\x00" not in ssid and b"\x00" not in password, "NUL forbidden")
        _require(
            hmac.compare_digest(wifi_profile_digest(ssid, password), wifi_digest),
            "wifi profile digest mismatch",
        )
        if unlock_digest is not None:
            observed = hashlib.sha256(bytes.fromhex(unlock_token)).hexdigest()
            _require(hmac.compare_digest(observed, unlock_digest), "unlock mismatch")
        return ActivateCommand(
            schema=ACTIVATE_SCHEMA,
            run_suffix=run_suffix,
            unlock_token_hex=unlock_token,
            persistence_key_hex=persistence_key,
            authorization_digest=authorization_digest,
            candidate_digest=candidate_digest,
            wifi_ssid=ssid,
            wifi_password=password,
            wifi_profile_digest=wifi_digest,
            broker_configuration_digest=broker_digest,
            raw_command_sha256=command_sha256(raw),
        )

    _require(len(fields) == 6, "VERIFY field count invalid")
    schema, run_suffix, unlock_token, persistence_key, active_digest, reserved = fields
    _run_suffix(run_suffix)
    _hex64(unlock_token, "unlock token")
    _hex64(persistence_key, "persistence key")
    _hex64(active_digest, "active digest")
    _require(reserved == "READ_ONLY", "VERIFY must be read-only")
    if unlock_digest is not None:
        observed = hashlib.sha256(bytes.fromhex(unlock_token)).hexdigest()
        _require(hmac.compare_digest(observed, unlock_digest), "unlock mismatch")
    return VerifyCommand(
        schema=VERIFY_SCHEMA,
        run_suffix=run_suffix,
        unlock_token_hex=unlock_token,
        persistence_key_hex=persistence_key,
        active_digest=active_digest,
        raw_command_sha256=command_sha256(raw),
    )


def redacted_summary(command: ParsedCommand) -> dict[str, object]:
    summary: dict[str, object] = {
        "schema": command.schema,
        "run_suffix_present": True,
        "unlock_token_present": True,
        "persistence_key_present": True,
        "raw_command_sha256": command.raw_command_sha256,
        "secret_values_included": False,
    }
    if isinstance(command, ActivateCommand):
        summary.update(
            {
                "authorization_digest_present": True,
                "candidate_digest_present": True,
                "wifi_profile_digest_present": True,
                "broker_configuration_digest_present": True,
                "wifi_credentials_present": True,
                "execution_action": "ACTIVATE_PROFILE",
            }
        )
    else:
        summary.update(
            {
                "active_digest_present": True,
                "read_only": True,
                "execution_action": "VERIFY_ACTIVE_READ_ONLY",
            }
        )
    return summary
