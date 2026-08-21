"""Fail-closed gates for N3-W Setup Secret handoff delivery."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import re
import sqlite3
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MAX_HANDOFF_BYTES = 4096
HANDOFF_KEYS = {"schema", "hardware_id", "pairing_id", "setup_secret"}


class DeliveryGateError(RuntimeError):
    """A delivery-gate error with a secret-safe public code."""


@dataclass(frozen=True)
class PendingSession:
    expires_at: datetime
    remaining_seconds: float


def _sha256(value: str | bytes) -> str:
    payload = value.encode("ascii") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def _absolute_regular_file(value: str, *, error_prefix: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise DeliveryGateError(f"{error_prefix}_PATH_MUST_BE_ABSOLUTE")
    if path.is_symlink() or not path.is_file():
        raise DeliveryGateError(f"{error_prefix}_NOT_REGULAR_FILE")
    return path


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise DeliveryGateError("REGISTRATION_EXPIRY_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise DeliveryGateError("REGISTRATION_EXPIRY_INVALID") from error
    if parsed.tzinfo is None:
        raise DeliveryGateError("REGISTRATION_EXPIRY_INVALID")
    return parsed.astimezone(UTC)


def _pending_session(
    database: Path,
    *,
    expected_hardware_id: str,
    expected_pairing_id_sha256: str,
    minimum_remaining_seconds: int,
    now: datetime,
) -> PendingSession:
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            """
            SELECT s.pairing_id, s.state, s.expires_at
            FROM pairing_sessions AS s
            JOIN registrations AS r
              ON r.hardware_id = s.hardware_id
             AND r.current_pairing_id = s.pairing_id
            WHERE s.hardware_id = ?
            """,
            (expected_hardware_id,),
        ).fetchall()
    finally:
        connection.close()

    matches = [
        row
        for row in rows
        if _sha256(str(row["pairing_id"])) == expected_pairing_id_sha256
    ]
    if len(matches) != 1:
        raise DeliveryGateError("EXACT_CURRENT_PAIRING_SESSION_NOT_UNIQUE")
    row = matches[0]
    if row["state"] != "pending":
        raise DeliveryGateError("EXACT_CURRENT_PAIRING_SESSION_NOT_PENDING")

    expires_at = _parse_timestamp(row["expires_at"])
    remaining_seconds = (expires_at - now.astimezone(UTC)).total_seconds()
    if remaining_seconds < minimum_remaining_seconds:
        raise DeliveryGateError("PENDING_TTL_MARGIN_INSUFFICIENT")
    return PendingSession(expires_at=expires_at, remaining_seconds=remaining_seconds)


def _validate_handoff(
    path: Path,
    *,
    expected_hardware_id: str,
    expected_pairing_id_sha256: str,
    expected_owner_uid: int,
    expected_owner_gid: int,
) -> str:
    metadata = path.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise DeliveryGateError("HANDOFF_MODE_INVALID")
    if metadata.st_uid != expected_owner_uid or metadata.st_gid != expected_owner_gid:
        raise DeliveryGateError("HANDOFF_OWNER_INVALID")
    if metadata.st_size <= 0 or metadata.st_size > MAX_HANDOFF_BYTES:
        raise DeliveryGateError("HANDOFF_SIZE_INVALID")

    payload = path.read_bytes()
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DeliveryGateError("HANDOFF_PAYLOAD_INVALID") from error
    if not isinstance(document, dict) or set(document) != HANDOFF_KEYS:
        raise DeliveryGateError("HANDOFF_PAYLOAD_INVALID")
    if document["schema"] != "gh.pair.setup-secret-import/1":
        raise DeliveryGateError("HANDOFF_SCHEMA_INVALID")
    if document["hardware_id"] != expected_hardware_id:
        raise DeliveryGateError("HANDOFF_HARDWARE_ID_MISMATCH")
    pairing_id = document["pairing_id"]
    setup_secret = document["setup_secret"]
    if not isinstance(pairing_id, str) or _sha256(pairing_id) != expected_pairing_id_sha256:
        raise DeliveryGateError("HANDOFF_PAIRING_ID_MISMATCH")
    if not isinstance(setup_secret, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", setup_secret):
        raise DeliveryGateError("HANDOFF_SETUP_SECRET_INVALID")
    try:
        decoded = base64.urlsafe_b64decode(setup_secret + "=")
    except ValueError as error:
        raise DeliveryGateError("HANDOFF_SETUP_SECRET_INVALID") from error
    if len(decoded) != 32:
        raise DeliveryGateError("HANDOFF_SETUP_SECRET_INVALID")
    return _sha256(payload)


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registration-db", required=True)
    parser.add_argument("--expected-hardware-id", required=True)
    parser.add_argument("--expected-pairing-id-sha256", required=True)
    parser.add_argument("--minimum-remaining-seconds", required=True, type=int)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate an exact pending session before an N3-W Setup Secret handoff delivery"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    pretransfer = subparsers.add_parser(
        "pretransfer",
        help="validate pending identity and TTL margin before transferring private material",
    )
    _add_common_arguments(pretransfer)
    predelivery = subparsers.add_parser(
        "predelivery",
        help="revalidate pending identity, TTL margin and staged handoff before atomic delivery",
    )
    _add_common_arguments(predelivery)
    predelivery.add_argument("--handoff", required=True)
    predelivery.add_argument("--expected-owner-uid", required=True, type=int)
    predelivery.add_argument("--expected-owner-gid", required=True, type=int)
    return parser


def main(argv: Sequence[str] | None = None, *, now: datetime | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not re.fullmatch(r"[0-9a-f]{64}", args.expected_pairing_id_sha256):
            raise DeliveryGateError("EXPECTED_PAIRING_ID_SHA256_INVALID")
        if args.minimum_remaining_seconds <= 0:
            raise DeliveryGateError("MINIMUM_REMAINING_SECONDS_INVALID")
        database = _absolute_regular_file(args.registration_db, error_prefix="REGISTRATION_DATABASE")
        observed_at = now or datetime.now(UTC)
        if observed_at.tzinfo is None:
            raise DeliveryGateError("OBSERVED_TIME_INVALID")
        session = _pending_session(
            database,
            expected_hardware_id=args.expected_hardware_id,
            expected_pairing_id_sha256=args.expected_pairing_id_sha256,
            minimum_remaining_seconds=args.minimum_remaining_seconds,
            now=observed_at,
        )

        handoff_sha256 = None
        if args.command == "predelivery":
            if args.expected_owner_uid < 0 or args.expected_owner_gid < 0:
                raise DeliveryGateError("HANDOFF_OWNER_EXPECTATION_INVALID")
            handoff = _absolute_regular_file(args.handoff, error_prefix="HANDOFF")
            handoff_sha256 = _validate_handoff(
                handoff,
                expected_hardware_id=args.expected_hardware_id,
                expected_pairing_id_sha256=args.expected_pairing_id_sha256,
                expected_owner_uid=args.expected_owner_uid,
                expected_owner_gid=args.expected_owner_gid,
            )
    except DeliveryGateError as error:
        print(f"DELIVERY_GATE=FAIL:{error}")
        print("PAIRING_ID_RAW_EXPOSED=false")
        print("SETUP_SECRET_EXPOSED=false")
        return 1
    except sqlite3.Error:
        print("DELIVERY_GATE=FAIL:REGISTRATION_DATABASE_INVALID")
        print("PAIRING_ID_RAW_EXPOSED=false")
        print("SETUP_SECRET_EXPOSED=false")
        return 1
    except OSError:
        print("DELIVERY_GATE=FAIL:DELIVERY_GATE_IO_FAILED")
        print("PAIRING_ID_RAW_EXPOSED=false")
        print("SETUP_SECRET_EXPOSED=false")
        return 1

    print("DELIVERY_GATE=PASS")
    print(f"DELIVERY_GATE_PHASE={args.command}")
    print(f"HARDWARE_ID_SHA256={_sha256(args.expected_hardware_id)}")
    print(f"PAIRING_ID_SHA256={args.expected_pairing_id_sha256}")
    print(f"PENDING_EXPIRES_AT={session.expires_at.isoformat().replace('+00:00', 'Z')}")
    print(f"PENDING_TTL_REMAINING_SECONDS={math.floor(session.remaining_seconds)}")
    if handoff_sha256 is not None:
        print(f"HANDOFF_SHA256={handoff_sha256}")
    print("PAIRING_ID_RAW_EXPOSED=false")
    print("SETUP_SECRET_EXPOSED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
