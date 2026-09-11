#!/usr/bin/env python3
"""N3W OTA Guard ROM identity contract repair R1.

This is a surgical successor adapter for the reviewed N3W OTA Guard v0.2.2
Board-B-recovery-only implementation. It does not replace or modify the reviewed
mutation core. It fixes one observed host-side identity parsing defect:

- esptool 5.2.0 on ESP32-C6 prints an 8-octet EUI64 ``MAC:`` line as well as a
  six-octet ``BASE MAC:`` line;
- the reviewed v0.2.2 generic six-octet regex can match the first six octets of
  the EUI64 line and therefore manufacture a second candidate;
- esptool's connection-info path and the explicit ``read-mac`` command can print
  the same BASE MAC more than once.

The repair accepts identity only from complete ``BASE MAC: <six-octet>`` lines,
requires exactly one distinct BASE MAC value across all such lines, preserves the
raw subprocess evidence, and passes a single canonical BASE MAC line to the
reviewed v0.2.2 expected-vs-observed comparison.

The reviewed base source is Git-blob-bound before any recovery workflow is
started. This adapter does not add app0 write, mutation retry, rollback, or any
new physical capability.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

REPAIR_NAME = "N3W OTA Guard ROM Identity Contract Repair"
REPAIR_REVISION = "identity-contract-r1"
EXPECTED_BASE_GIT_BLOB = "e7b0019cdb9673fbf4e23653dec561ea40ff757c"
BASE_SOURCE_PATH = Path(__file__).with_name("n3w_ota_guard.py")

_BASE_MAC_LINE_RE = re.compile(
    r"(?im)^[ \t]*BASE MAC:[ \t]*"
    r"((?:[0-9a-f]{2}:){5}[0-9a-f]{2})[ \t]*$"
)


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # Git object identity, not crypto auth


def verify_reviewed_base_binding() -> str:
    if not BASE_SOURCE_PATH.is_file():
        raise RuntimeError("reviewed N3W OTA Guard base source is missing")
    observed = git_blob_sha1(BASE_SOURCE_PATH)
    if observed != EXPECTED_BASE_GIT_BLOB:
        raise RuntimeError("reviewed N3W OTA Guard base Git blob mismatch")
    return observed


def _load_reviewed_base():
    verify_reviewed_base_binding()
    spec = importlib.util.spec_from_file_location(
        "n3w_ota_guard_reviewed_base", BASE_SOURCE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load reviewed N3W OTA Guard base source")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = _load_reviewed_base()


def extract_authoritative_base_mac(output: str) -> tuple[str, int]:
    """Return the one distinct exact BASE MAC value and its line occurrence count.

    Generic ``MAC:`` lines, EUI64 values, MAC_EXT values, and six-octet substrings
    embedded inside longer values are deliberately ignored.
    """
    if not isinstance(output, str):
        raise base.GuardError("ROM identity output is not textual")

    matches = [base.normalize_mac(value) for value in _BASE_MAC_LINE_RE.findall(output)]
    distinct = set(matches)
    if not matches:
        raise base.GuardError("ROM identity output contains no exact BASE MAC line")
    if len(distinct) != 1:
        raise base.GuardError(
            "ROM identity output contains multiple distinct exact BASE MAC values"
        )
    return next(iter(distinct)), len(matches)


def replay_identity_evidence(stdout_path: str, expected_base_mac: str) -> tuple[int, int]:
    """Host-only replay of already captured read-mac stdout against private identity."""
    path = Path(stdout_path).expanduser().resolve()
    if not path.is_file():
        raise base.GuardError("identity stdout evidence file is missing")
    output = path.read_text(encoding="utf-8")
    observed, occurrence_count = extract_authoritative_base_mac(output)
    expected = base.normalize_mac(expected_base_mac)
    if observed != expected:
        raise base.GuardError("replayed exact BASE MAC does not match expected identity")
    return occurrence_count, 1


def identity_contract_runner(argv, evidence, label):
    """Delegate all I/O to reviewed base runner; canonicalize identity result only."""
    result = base.run_read_command(argv, evidence, label)
    if label != "rom_identity_read":
        return result

    output = getattr(result, "stdout", "")
    observed, occurrence_count = extract_authoritative_base_mac(output)

    all_six_octet = {
        base.normalize_mac(value)
        for value in re.findall(
            r"(?i)(?<![0-9a-f:])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?!:[0-9a-f]{2})",
            output,
        )
    }
    evidence.write_json(
        "rom-identity-contract-repair.json",
        {
            "repair_name": REPAIR_NAME,
            "repair_revision": REPAIR_REVISION,
            "reviewed_base_git_blob": EXPECTED_BASE_GIT_BLOB,
            "raw_stdout_preserved": True,
            "authoritative_label": "BASE MAC",
            "authoritative_line_occurrence_count": occurrence_count,
            "authoritative_distinct_value_count": 1,
            "bounded_six_octet_distinct_value_count": len(all_six_octet),
            "eui64_substring_candidates_ignored": True,
            "canonicalized_stdout_for_reviewed_parser": True,
        },
    )

    return subprocess.CompletedProcess(
        args=getattr(result, "args", list(argv)),
        returncode=getattr(result, "returncode", 0),
        stdout=f"BASE MAC: {observed}\n",
        stderr=getattr(result, "stderr", ""),
    )


def execute_recovery_app0_to_slot0(
    python_exe: str,
    esptool_path: str,
    port: str,
    evidence_dir: str,
    *,
    expected_base_mac: str,
    authorization_id: str,
):
    verify_reviewed_base_binding()
    return base.execute_recovery_app0_to_slot0(
        python_exe,
        esptool_path,
        port,
        evidence_dir,
        expected_base_mac=expected_base_mac,
        authorization_id=authorization_id,
        runner=identity_contract_runner,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-ota-guard-identity-repair")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--esptool", help="exact ESP-IDF v5.5.4 esptool.py wrapper"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check-repair-binding")
    check.add_argument("--quiet", action="store_true")

    replay = sub.add_parser("replay-identity-evidence")
    replay.add_argument("--stdout-file", required=True)
    replay.add_argument("--expected-base-mac", required=True)

    recover = sub.add_parser("recover-app0-to-slot0")
    recover.add_argument("--port", required=True)
    recover.add_argument("--evidence-dir", required=True)
    recover.add_argument("--expected-base-mac", required=True)
    recover.add_argument("--authorization-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        base_blob = verify_reviewed_base_binding()
        if args.command == "check-repair-binding":
            if not args.quiet:
                print(f"REPAIR_REVISION={REPAIR_REVISION}")
                print(f"REVIEWED_BASE_GIT_BLOB={base_blob}")
                print("REPAIR_BINDING=PASS")
            return 0

        if args.command == "replay-identity-evidence":
            occurrence_count, distinct_count = replay_identity_evidence(
                args.stdout_file, args.expected_base_mac
            )
            print("IDENTITY_REPAIR_REPLAY=PASS")
            print(f"AUTHORITATIVE_BASE_MAC_LINE_COUNT={occurrence_count}")
            print(f"AUTHORITATIVE_DISTINCT_BASE_MAC_COUNT={distinct_count}")
            print("EXPECTED_IDENTITY_MATCH=PASS")
            print("BOARD_ACCESS=false")
            return 0

        if args.command == "recover-app0-to-slot0":
            if not args.esptool:
                raise base.GuardError("physical recovery requires --esptool")
            result = execute_recovery_app0_to_slot0(
                args.python,
                args.esptool,
                args.port,
                args.evidence_dir,
                expected_base_mac=args.expected_base_mac,
                authorization_id=args.authorization_id,
            )
            print("RECOVERY_RESULT=PASS")
            print(f"EVIDENCE_DIR={result.evidence_dir}")
            return 0

        raise base.GuardError("unknown repair-adapter command")
    except (base.GuardError, RuntimeError, OSError, subprocess.SubprocessError, ImportError) as exc:
        print(f"N3W_OTA_GUARD_IDENTITY_REPAIR_FAIL={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
