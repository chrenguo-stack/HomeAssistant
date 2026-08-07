#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "2d444f3e392249c8d7bf1a1aa036e738a418d1cb"
BASE_REF = (
    "feature/c06b2b-recorder-readback-utc-canonicalization-pr266-successor-20260804-v1"
)
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
    model = (ROOT / FILES[3 + 1]).read_text()
    checks = {
        "exact_base_bound": entry.get("base") == {"ref": BASE_REF, "sha": BASE_SHA},
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
        in (ROOT / FILES[2 + 1]).read_text()
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
    base_ref = os.getenv("GITHUB_BASE_REF", "")
    if base_ref:
        if base_ref != BASE_REF or os.getenv("N3W_ACTUAL_BASE_SHA") != BASE_SHA:
            failures.append("github_base_mismatch")
        changed = subprocess.run(
            ("git", "diff", "--name-only", f"{BASE_SHA}...HEAD"),
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        allowed = {str(path) for path in FILES}
        if any(path not in allowed for path in changed):
            failures.append("change_scope_expanded")
    report = {
        "schema": "gh.n3w-single-hop-contract-gate/1",
        "status": "passed" if not failures else "failed",
        "base_ref": BASE_REF,
        "base_sha": BASE_SHA,
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
