#!/usr/bin/env python3
"""Build a public-only Stage 2D-9R exact D2 authorization review package.

This tool creates review material only. It never creates an authorization
record or an execution launcher and never accesses a board, serial port,
network service, Broker, Flash, NVS, or private custody content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

STAGE = "H3/N2 Stage 2D-9R G3R"
REPOSITORY = "chrenguo-stack/HomeAssistant"
BRANCH = "feature/h3-n2-stage2d9r-g3-tls-valid-candidate-20260723-v1"
PR_NUMBER = 176
EXPECTED_MAIN_SHA = "a3a72d75480362999e70e180f33459198b3951b5"
D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-20260725-01"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

PUBLIC_BINDINGS = {
    "immutable_artifact_id": 8585140964,
    "immutable_artifact_github_digest_sha256": "ecc28451499e0d2d934c7e298037ed5ee156c887bf72a9b258101c4aef7e2808",
    "immutable_payload_sha256": "5dbe763fe411728533018dd324075f5287ee3542f8351113d54ec80a7042f1d3",
    "immutable_application_sha256": "7651a6476cd48dda6aa5e400695e126b91141c95fca5b74d879f65f2058d1630",
    "immutable_merged_sha256": "ea6af469ad7ae103d40a551f482fc18d1f2afc9ed75933481f1802f0a7b2916f",
    "immutable_source_sha": "c9e8447c24b0f09f3eac3f56791f2346e8aa5d61",
    "recovery_artifact_id": 8589561310,
    "recovery_artifact_github_digest_sha256": "f1654002f894ec136f4b52248a6b0e26ed9dedc7460e8205ec9f852b161d4a6a",
    "recovery_payload_sha256": "c1ed8e5f00b17cbe5bab30aec75d2e8637986b9c19b2389b761bebf3fc0b8d8b",
    "recovery_manifest_sha256": "fe82c458533953df4c86966d047d1f66b59da15e5299b3953135702236d68690",
    "recovery_erased_sha256": "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063",
    "recovery_source_sha": "f312f8580d9f4312f4dd1429b2d7755e1c550636",
    "command_private_package_sha256": "cc9086c20781007655c498b78ff1ce7af3316db0c02edbae2440d177d7fdfbb5",
    "unlock_digest_sha256": "3650d44f8761f21dc1931fbd9b6ba6a1d9da92ffa469b3d4f98ee5411a6809e3",
    "pki_private_package_sha256": "0632b37a70aa2eae416c48ffa9420a8f1e13788c22a7d12e211f77cf6e78a267",
    "ca_pem_sha256": "cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963",
    "broker_certificate_sha256": "988b6f82b04b0b3cf13f58a07ecd85e420e5576c167fe01ea0940d4530e20ac7",
    "broker_spki_sha256": "f034dc2a036f709287f0558773418ee1799e75bee50dcf55e09143a3a9052a03",
    "candidate_digest_sha256": "f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5",
    "u1_04_authorization_record_sha256": "f9d02e196fa884be7b72a18849bd59aa902512bc5cfac8f20b10ecd20fdf9ed8",
    "u1_04_private_content_binding_sha256": "d1cd5f72134a19f0748869990e4ff15f61ac0df02331b74ad57a603d35c617a7",
    "u1_04_consumed_marker_sha256": "0f4cf491548527d0c8339f1261777420952db9c59805badeafc55b62dba0d8dc",
    "python_executable_sha256": "4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a",
    "openssl_executable_sha256": "04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973",
}

FUTURE_SEQUENCE = [
    "READ_ONLY_IDENTIFY_CURRENT_V69_STATE",
    "LOCKED_RECOVERY_TO_DETERMINISTIC_BASELINE",
    "RECOVERY_READBACK_AND_SEED_VERIFY",
    "ERASE_AND_FLASH_STAGE2D9R_IMMUTABLE_FIRMWARE",
    "FLASH_VERIFY_AND_AUTOMATIC_HARD_RESET",
    "START_EXACT_ISOLATED_TLS_BROKER",
    "GH2D9R_PREPARE_V1_EXACTLY_ONCE",
    "FIRMWARE_AUTOMATIC_RESTART",
    "GH2D9R_VERIFY_V1_READ_ONLY_EXACTLY_ONCE",
    "STOP_ISOLATED_BROKER_AND_RETAIN_PRIVATE_EVIDENCE",
]

PROHIBITED = [
    "AUTHORIZATION_REPLAY",
    "AUTOMATIC_RETRY",
    "ACTIVATE_PROFILE",
    "CLEANUP_TEST_STATE",
    "PRODUCTION_BROKER_OR_CREDENTIALS",
    "HOME_ASSISTANT",
    "GREENHOUSE_MANAGER",
    "M401A",
    "T1",
    "EFUSE",
    "SECURE_BOOT",
    "FLASH_ENCRYPTION",
    "READY",
    "MERGE",
    "RELEASE",
    "TAG",
    "DEPLOYMENT",
]


class ReviewPackageError(RuntimeError):
    """Fail-closed public review packager error."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReviewPackageError(code)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_text(path: Path, value: str, mode: int = 0o600) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")
    os.chmod(path, mode)


def build_binding(source_sha: str, main_sha: str) -> dict[str, Any]:
    require(HEX40.fullmatch(source_sha) is not None, "SOURCE_SHA_INVALID")
    require(main_sha == EXPECTED_MAIN_SHA, "MAIN_SHA_MISMATCH")
    binding: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-d2-review-binding/1",
        "state": "PENDING_EXACT_D2_REVIEW",
        "stage": STAGE,
        "d2_request_id": D2_REQUEST_ID,
        "repository": REPOSITORY,
        "branch": BRANCH,
        "pull_request": PR_NUMBER,
        "required_pull_request_state": {
            "state": "open",
            "draft": True,
            "merged": False,
            "mergeable": True,
        },
        "main_sha": main_sha,
        "source_sha": source_sha,
        "all_current_head_ci_success_required": True,
        "artifact_expiry_recheck_required": True,
        "live_pr_and_main_recheck_required": True,
        "u1_04_status": "CONSUMED",
        "u1_04_replay_permitted": False,
        "automatic_retry_permitted": False,
        "future_authorization_duration_seconds_max": 7200,
        "future_sequence": FUTURE_SEQUENCE,
        "prohibited_operations": PROHIBITED,
        "public_bindings": PUBLIC_BINDINGS,
        "authorization_record_included": False,
        "authorized_execution_launcher_included": False,
        "private_content_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "network_operation": False,
        "broker_started": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "prepare_executed": False,
        "verify_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
    }
    binding["review_binding_sha256"] = sha256_bytes(canonical_json_bytes(binding))
    return binding


def authorization_text(binding: dict[str, Any]) -> str:
    p = binding["public_bindings"]
    return f"""D2 authorization request: {binding['d2_request_id']}

This is a review template only. It is not an authorization record and must not
be executed as a command.

Exact future authorization must bind:
repository={binding['repository']}
pull_request={binding['pull_request']}
pull_request_state=open,draft,unmerged,mergeable
main_sha={binding['main_sha']}
source_sha={binding['source_sha']}
review_binding_sha256={binding['review_binding_sha256']}
immutable_artifact_id={p['immutable_artifact_id']}
immutable_artifact_github_digest_sha256={p['immutable_artifact_github_digest_sha256']}
recovery_artifact_id={p['recovery_artifact_id']}
recovery_artifact_github_digest_sha256={p['recovery_artifact_github_digest_sha256']}
u1_04_status=CONSUMED
u1_04_authorization_record_sha256={p['u1_04_authorization_record_sha256']}
u1_04_private_content_binding_sha256={p['u1_04_private_content_binding_sha256']}
u1_04_consumed_marker_sha256={p['u1_04_consumed_marker_sha256']}
candidate_digest_sha256={p['candidate_digest_sha256']}

The future D2 must be exact, one-shot, no-replay, no-automatic-retry and no
longer than two hours. Success or failure consumes it. Any drift before claim
must stop without consuming it and requires a new request.

No authorization is granted by this file.
"""


def command_sequence_text() -> str:
    lines = ["# Reviewed future D2 sequence", "", "This document is descriptive only.", ""]
    for index, operation in enumerate(FUTURE_SEQUENCE, 1):
        lines.append(f"{index}. `{operation}`")
    lines.extend(
        [
            "",
            "There is no ACTIVATE or CLEANUP operation in Stage 2D-9R.",
            "Exactly one PREPARE and exactly one read-only VERIFY are permitted only",
            "after a future exact D2 has been separately granted.",
            "",
        ]
    )
    return "\n".join(lines)


def stop_conditions_text() -> str:
    return """# Fail-closed stop conditions

Stop before claim, without consuming a future D2, if any of these changes:

- PR state, Draft state, merge state, mergeability, main SHA or source SHA;
- any current-HEAD CI result;
- immutable or recovery Artifact ID, digest, expiry or source/run binding;
- U1-04 record, result, consumed marker or custody binding;
- toolchain, candidate, command package, PKI package, CA or Broker identity;
- board identity, USB/serial candidate set, power state or recovery baseline.

After claim, success or failure consumes the future D2. No automatic retry,
replay, alternate command, manual mutation, ACTIVATE, CLEANUP or production
operation is permitted.
"""


def readme_text(binding: dict[str, Any], launcher_name: str) -> str:
    return f"""# Stage 2D-9R exact D2 review package

State: `PENDING_EXACT_D2_REVIEW`

This package is public-only and review-only. It contains no authorization
record, no execution launcher, no private key, no password, no unlock token and
no private custody path. It performs no network, Broker, board, serial, Flash,
NVS, PREPARE, VERIFY, ACTIVATE, CLEANUP or production operation.

Run `{launcher_name}` only to verify this package's checksums and print safe
review metadata. The launcher does not grant D2 and cannot execute the reviewed
future sequence.

A future exact authorization may be requested only after all CI for source
`{binding['source_sha']}` is completed successfully and live PR, main, Artifact,
U1-04 and custody bindings have been rechecked.
"""


def assemble(output: Path, source_sha: str, main_sha: str) -> dict[str, Any]:
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)

    binding = build_binding(source_sha, main_sha)
    launcher_name = (
        "run_stage2d9r_d2_review_integrity_probe_20260725_v1_"
        + binding["review_binding_sha256"][:8]
        + ".sh"
    )

    write_text(
        output / "D2_REVIEW_BINDING.json",
        json.dumps(binding, indent=2, sort_keys=True) + "\n",
    )
    write_text(output / "D2_AUTHORIZATION_REQUEST.txt", authorization_text(binding))
    write_text(output / "COMMAND_SEQUENCE.md", command_sequence_text())
    write_text(output / "STOP_CONDITIONS.md", stop_conditions_text())
    write_text(output / "README.md", readme_text(binding, launcher_name))

    launcher = f"""#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
cd "$ROOT"
shasum -a 256 -c SHA256SUMS
PYTHONDONTWRITEBYTECODE=1 "$(command -v python3)" - <<'PY'
import json
from pathlib import Path
b = json.loads(Path("D2_REVIEW_BINDING.json").read_text(encoding="utf-8"))
print("STAGE2D9R_D2_REVIEW_INTEGRITY_PROBE_V1_BEGIN")
for key in (
    "state", "d2_request_id", "repository", "pull_request", "main_sha",
    "source_sha", "review_binding_sha256",
    "authorization_record_included", "authorized_execution_launcher_included",
    "private_content_included", "network_operation", "broker_started",
    "board_operation", "serial_operation", "flash_operation",
    "physical_nvs_operation", "prepare_executed", "verify_executed",
):
    print(f"{{key}}={{str(b[key]).lower() if isinstance(b[key], bool) else b[key]}}")
print("STAGE2D9R_D2_REVIEW_INTEGRITY_PROBE_V1_END")
PY
"""
    write_text(output / launcher_name, launcher, mode=0o700)

    entries = []
    for path in sorted(output.iterdir(), key=lambda item: item.name):
        if path.name == "SHA256SUMS":
            continue
        entries.append(f"{sha256_file(path)}  {path.name}")
    write_text(output / "SHA256SUMS", "\n".join(entries) + "\n")

    return {
        "schema": "gh.h3.n2.stage2d9r-d2-review-package-summary/1",
        "state": binding["state"],
        "d2_request_id": binding["d2_request_id"],
        "source_sha": source_sha,
        "main_sha": main_sha,
        "review_binding_sha256": binding["review_binding_sha256"],
        "launcher": launcher_name,
        "authorization_record_included": False,
        "authorized_execution_launcher_included": False,
        "private_content_included": False,
        "network_operation": False,
        "broker_started": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "prepare_executed": False,
        "verify_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--main-sha", required=True)
    args = parser.parse_args()
    try:
        result = assemble(
            args.output.expanduser().resolve(strict=False),
            args.source_sha,
            args.main_sha,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ReviewPackageError) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
