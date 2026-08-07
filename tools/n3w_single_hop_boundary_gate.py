#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_BASE_SHA = "2d444f3e392249c8d7bf1a1aa036e738a418d1cb"
SOURCE_BASE_REF = (
    "feature/c06b2b-recorder-readback-utc-canonicalization-pr266-successor-20260804-v1"
)
CURRENT_MAIN_INTEGRATION_SHA = "c08989bbbc745f45177819c3d9b323798bbcae3b"
CURRENT_MAIN_INTEGRATION_REF = "main"
PRESERVED_SOURCE_SHA = "239ea594c643d4990d449187f8b0cabae619e3d7"
FILES = (
    Path("docs/decisions/n3w-stage-entry.json"),
    Path("protocols/transport/gh-n3w-single-hop-v1.md"),
    Path("protocols/README.md"),
    Path("experiments/n3w_single_hop/__init__.py"),
    Path("experiments/n3w_single_hop/model.py"),
    Path("experiments/n3w_single_hop/test_model.py"),
    Path("tools/n3w_single_hop_boundary_gate.py"),
    Path(".github/workflows/n3w-single-hop-contract-ci.yml"),
)
SEMANTIC_FILES = FILES[:6]


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    failures: list[str] = []
    for relative in FILES:
        if not (ROOT / relative).is_file():
            failures.append(f"missing:{relative}")
    entry = json.loads((ROOT / FILES[0]).read_text())
    protocol = (ROOT / FILES[1]).read_text()
    model = (ROOT / FILES[4]).read_text()
    checks = {
        "exact_source_base_bound": entry.get("base")
        == {"ref": SOURCE_BASE_REF, "sha": SOURCE_BASE_SHA},
        "prerequisites_closed": all(
            entry["prerequisites"][name].get(
                "ancestor_of_base", entry["prerequisites"][name].get("exact_base")
            )
            is True
            for name in ("n2", "h0_h1", "c06")
        ),
        "single_hop_only": "hop_count` 只能为 1" in protocol and "Mesh" in protocol,
        "aead_contract": all(
            token in protocol
            for token in ("AES-256-GCM", "96-bit nonce", "AAD", "应用层 AEAD")
        ),
        "path_identity_stable": all(
            token in protocol
            for token in (
                "第二个 NODE_ID",
                "第二套 Discovery",
                "node_id + boot_id + seq",
            )
        ),
        "experimental_not_production": "not wired to production entry points"
        in (ROOT / FILES[3]).read_text()
        and 'firmware_driver": false' in (ROOT / FILES[0]).read_text(),
        "no_network_or_process_api": all(
            token not in model
            for token in (
                "socket",
                "subprocess",
                "paho",
                "requests",
                "docker",
                "esp_now_send",
            )
        ),
    }
    failures.extend(name for name, passed in checks.items() if not passed)

    base_ref = os.getenv("GITHUB_BASE_REF", "") or os.getenv("N3W_ACTUAL_BASE_REF", "")
    actual_base_sha = os.getenv("N3W_ACTUAL_BASE_SHA", "")
    actual_head_sha = os.getenv("N3W_ACTUAL_HEAD_SHA", "HEAD") or "HEAD"
    integration_mode = "local"
    semantic_byte_identity = True
    preserved_source_ancestor = True
    current_main_ancestor = True

    if base_ref:
        if base_ref == SOURCE_BASE_REF:
            integration_mode = "source_stack"
            if actual_base_sha != SOURCE_BASE_SHA:
                failures.append("github_base_mismatch")
            diff_base = SOURCE_BASE_SHA
        elif base_ref == CURRENT_MAIN_INTEGRATION_REF:
            integration_mode = "current_main_successor"
            if actual_base_sha != CURRENT_MAIN_INTEGRATION_SHA:
                failures.append("github_base_mismatch")
            current_main_ancestor = (
                _git(
                    "merge-base",
                    "--is-ancestor",
                    CURRENT_MAIN_INTEGRATION_SHA,
                    actual_head_sha,
                    check=False,
                ).returncode
                == 0
            )
            preserved_source_ancestor = (
                _git(
                    "merge-base",
                    "--is-ancestor",
                    PRESERVED_SOURCE_SHA,
                    actual_head_sha,
                    check=False,
                ).returncode
                == 0
            )
            semantic_byte_identity = (
                _git(
                    "diff",
                    "--quiet",
                    PRESERVED_SOURCE_SHA,
                    actual_head_sha,
                    "--",
                    *(str(path) for path in SEMANTIC_FILES),
                    check=False,
                ).returncode
                == 0
            )
            if not current_main_ancestor:
                failures.append("current_main_not_ancestor")
            if not preserved_source_ancestor:
                failures.append("preserved_source_not_ancestor")
            if not semantic_byte_identity:
                failures.append("preserved_source_semantic_drift")
            diff_base = CURRENT_MAIN_INTEGRATION_SHA
        else:
            failures.append("github_base_mismatch")
            diff_base = SOURCE_BASE_SHA

        changed = _git(
            "diff", "--name-only", f"{diff_base}...{actual_head_sha}"
        ).stdout.splitlines()
        allowed = {str(path) for path in FILES}
        if any(path not in allowed for path in changed):
            failures.append("change_scope_expanded")
        if integration_mode == "current_main_successor" and set(changed) != allowed:
            failures.append("current_main_successor_file_set_mismatch")

    report = {
        "schema": "gh.n3w-single-hop-contract-gate/1",
        "status": "passed" if not failures else "failed",
        "source_base_ref": SOURCE_BASE_REF,
        "source_base_sha": SOURCE_BASE_SHA,
        "integration_mode": integration_mode,
        "integration_base_ref": base_ref or None,
        "integration_base_sha": actual_base_sha or None,
        "preserved_source_sha": PRESERVED_SOURCE_SHA,
        "preserved_source_ancestor": preserved_source_ancestor,
        "current_main_ancestor": current_main_ancestor,
        "semantic_byte_identity": semantic_byte_identity,
        "checks": checks,
        "failures": failures,
        "file_sha256": {
            str(path): hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in FILES
            if (ROOT / path).is_file()
        },
        "production_wiring": False,
        "board_or_live_executed": False,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text, end="")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
