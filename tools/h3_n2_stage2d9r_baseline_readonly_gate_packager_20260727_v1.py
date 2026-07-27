#!/usr/bin/env python3
"""Build a public, non-authorizing baseline-readonly review Artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "docs/decisions/h3-n2-stage2d9r-baseline-readonly-gate-d1-20260727-v1.json",
    "docs/development/h3-n2-stage2d9r-baseline-readonly-gate-contract-20260727-v1.md",
    "tools/h3_n2_stage2d9r_consumed_marker_evidence_20260727_v1.py",
    "tools/h3_n2_stage2d9r_baseline_readonly_gate_20260727_v1.py",
    "tools/h3_n2_stage2d9r_d2_readonly_preflight_v3_20260727.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_consumed_marker_evidence_20260727_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_baseline_readonly_gate_20260727_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_d2_readonly_preflight_v3_20260727.py",
)


class PackageError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PackageError(code)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def copy_regular(source: Path, destination: Path) -> None:
    require(source.is_file() and not source.is_symlink(), "SOURCE_FILE_INVALID")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o600)


def build(output: Path, source_sha: str, base_sha: str, main_sha: str) -> dict[str, Any]:
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    require(len(source_sha) == len(base_sha) == len(main_sha) == 40,
            "SOURCE_BINDING_INVALID")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)

    for relative in FILES:
        copy_regular(ROOT / relative, output / relative)

    binding: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-successor-baseline-readonly-gate-review-binding/1",
        "stage": "H3/N2 Stage 2D-9R G3R successor",
        "d1_decision_id": "D1-H3N2-STAGE2D9R-G3R-BASELINE-READONLY-GATE-20260727-01",
        "future_authorization_id": "D2-H3N2-STAGE2D9R-G3R-BASELINE-READONLY-20260727-01",
        "repository": "chrenguo-stack/HomeAssistant",
        "source_sha": source_sha,
        "base_sha": base_sha,
        "main_sha": main_sha,
        "artifact_purpose": "SOURCE_REVIEW_TEST_AND_FREEZE_ONLY",
        "marker_only_consumed_evidence_supported": True,
        "original_u1_files_reconstructed": False,
        "original_u1_authorization_replayed": False,
        "physical_execution_authorized": False,
        "authorization_record_included": False,
        "execution_launcher_included": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_read_operation": False,
        "flash_erase_operation": False,
        "flash_write_operation": False,
        "flash_verify_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
        "ready_authorized": False,
        "merge_authorized": False,
        "release_authorized": False,
        "deployment_authorized": False,
    }
    binding["binding_sha256"] = canonical_sha256(binding)
    binding_path = output / "BASELINE_READONLY_GATE_REVIEW_BINDING.json"
    binding_path.write_text(
        json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.chmod(binding_path, 0o600)

    readme = """# Stage2D9R baseline-readonly gate review package

This package is public review material only. It records the approved D1,
validates marker-only consumed U1 evidence, and freezes a future exact one-shot
read-only board-baseline collector.

It contains no authorization record and no execution launcher. Do not connect a
board or invoke the physical collector from this review package.
"""
    readme_path = output / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    os.chmod(readme_path, 0o600)

    probe = output / "run_stage2d9r_baseline_readonly_gate_review_integrity_probe_20260727_v1.sh"
    probe.write_text(
        """#!/bin/sh
set -eu
cd "$(dirname "$0")"
sha256sum -c SHA256SUMS
python3 - <<'PY'
import json
from pathlib import Path
v=json.loads(Path("BASELINE_READONLY_GATE_REVIEW_BINDING.json").read_text())
assert v["physical_execution_authorized"] is False
assert v["authorization_record_included"] is False
assert v["execution_launcher_included"] is False
assert v["board_operation"] is False
assert v["network_operation"] is False
print("STAGE2D9R_BASELINE_READONLY_GATE_REVIEW_INTEGRITY=PASS")
print("physical_execution_authorized=false")
print("authorization_record_included=false")
print("execution_launcher_included=false")
PY
""",
        encoding="utf-8",
    )
    os.chmod(probe, 0o700)

    sums = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(f"{sha256_file(path)}  {path.relative_to(output)}")
    sums_path = output / "SHA256SUMS"
    sums_path.write_text("\n".join(sums) + "\n", encoding="utf-8")
    os.chmod(sums_path, 0o600)
    return binding


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--main-sha", required=True)
    args = parser.parse_args()
    try:
        binding = build(args.output, args.source_sha, args.base_sha, args.main_sha)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, PackageError) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "PASS",
        "binding_sha256": binding["binding_sha256"],
        "physical_execution_authorized": False,
        "board_operation": False,
        "network_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
