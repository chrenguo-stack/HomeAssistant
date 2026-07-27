#!/usr/bin/env python3
"""Assemble the non-authorizing Stage2D9R D2 V3 host-only final preflight.

The generated package performs metadata/hash validation only on the operator
host. It has no board, serial, Flash, NVS, network, Broker, PREPARE, VERIFY,
ACTIVATE or CLEANUP command path and cannot create or claim a D2 authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

AUTHORIZATION_ID = "D2-H3N2-STAGE2D9R-G3R-SUCCESSOR-20260727-01"
BASELINE_AUTHORIZATION_ID = (
    "D2-H3N2-STAGE2D9R-G3R-BASELINE-READONLY-20260727-01"
)
SOURCE_BASE_SHA = "4a5b7a5290f04500050783124f9711268dba0afd"
PR180_SHA = "b2c481d5c824bd6606d914f5828ba6a1662000b1"
PR176_SHA = "cf841f3e5a8cf04c5df9875c499b91ad4e4289cb"
MAIN_SHA = "43aa37b0cc343efdd2024f369517e55c5b6461f1"
PYTHON_SHA256 = "4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a"
OPENSSL_SHA256 = "04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973"

REVIEW_ARTIFACT_ID = 8645580706
REVIEW_ARTIFACT_DIGEST = (
    "26bb34863a33fcf0b02d6f36ffa39ad1f1daa2ae6137eae6e4f063ab2752d88d"
)
PUBLIC_PREFLIGHT_ARTIFACT_ID = 8645581131
PUBLIC_PREFLIGHT_ARTIFACT_DIGEST = (
    "ba0ad72df54893a16e9ce9dbd558eb7b6140ad1ddaff5ebf31f5632dabaeb965"
)
RECOVERY_ARTIFACT_ID = 8644594652
RECOVERY_ARTIFACT_DIGEST = (
    "3274a9329f46f420b65037efdf3cb9e453121ec7f74573430fb2afc8a7de882e"
)
RECOVERY_SOURCE_SHA = "f26ceafcfddec9abc1f8b023451ebe0747f2442b"
EXECUTION_ARTIFACT_ID = 8644968239
EXECUTION_ARTIFACT_DIGEST = (
    "d15928b1930b39871f16a67b768718466ffcd4ed2f4ad0eaefbc424c9a1ca33f"
)
EXECUTION_SOURCE_SHA = "623f2cddf7ed121952eb8644abe681aa11b5677b"
HOST_PROBE_ARTIFACT_ID = 8645578982
HOST_PROBE_ARTIFACT_DIGEST = (
    "81d5418bc6ede45ecf6208e2155839b0361685bec50df46556de9319d47e02bb"
)
BASELINE_ACCEPTANCE_ARTIFACT_ID = 8652416395
BASELINE_ACCEPTANCE_ARTIFACT_DIGEST = (
    "cab3cc8cc2060176684e1a7b25fb45122d34c5d983e12298bea189e20725ef32"
)

BASELINE_RESULT_SHA256 = (
    "83de8568ddfe73fc98c1408c1347a9817b03c4a9adb4ef091990d9b3b39ceab9"
)
BOARD_IDENTITY_SHA256 = (
    "2607b7df80b8b636548a8d9d97c0a6b4e4ead57e9a2cc6fcb7f93643617242f8"
)
SERIAL_IDENTITY_SHA256 = (
    "b6dba7ee0db02feba166935ae8ec2bbd946dbf66926e5421cfa1c1c8b8a4f2c3"
)
BASELINE_STATE_SHA256 = (
    "15ad524c4328fd93c99a10e1e0955080e5dedeb8df371832c4d437538dc8944a"
)
TEST_PARTITION_SHA256 = (
    "a8438e656e6b3327506a988136884113c8df8ed012373b851ea2c6da681e8b7b"
)

EXECUTION_PACKAGE_SHA256 = (
    "d01aeb81b3c23b38061f17e3e32f807b0ceffd79c87cd79d9d47e24f42446112"
)
EXECUTION_SCRIPT_SHA256 = (
    "1fa9428e940f65e98716f20a5ae78904c96db53e94bdfb0ee5da845894c6d3aa"
)
EXECUTION_LAUNCHER_SHA256 = (
    "e084a1173d061bb414801bf9cf189c5a11db0590df9a562cd35551fef287cdd3"
)
EXECUTION_MARKER_NAME_SHA256 = (
    "034e7357d0e7cea177c20cc4ea257a72a9a1a9eb02318cef47f5d43ee32f5987"
)
LOCKED_RECOVERY_PACKAGE_SHA256 = (
    "50c4ff6569401b3c1cb20570ed149b0a5978fdc202c2aa33dff1b6ea1fe58d2e"
)

REPOSITORY_FILES = (
    "docs/decisions/h3-n2-stage2d9r-d2-v3-final-preflight-host-readonly-20260727-v1.json",
    "docs/acceptance/h3-n2-stage2d9r-baseline-readonly-d2-acceptance-20260727-v1.json",
    "docs/acceptance/h3-n2-stage2d9r-successor-locked-recovery-artifact-l1-v1.json",
    "docs/acceptance/h3-n2-stage2d9r-successor-d2-execution-package-l1-v1.json",
    "tools/h3_n2_stage2d9r_d2_readonly_preflight_v3_20260727.py",
    "tools/h3_n2_stage2d9r_consumed_marker_evidence_20260727_v1.py",
    "tools/h3_n2_stage2d9r_successor_d2_readonly_preflight_20260727_v2.py",
    "tools/h3_n2_stage2d9r_successor_d2_readonly_preflight_20260727_v1.py",
    "tools/h3_n2_stage2d9r_successor_d2_contract_20260727_v1.py",
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


def copy_regular(source: Path, destination: Path, mode: int = 0o600) -> None:
    require(source.is_file() and not source.is_symlink(), "SOURCE_FILE_INVALID")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    os.chmod(destination, mode)


def copy_tree(source: Path, destination: Path) -> None:
    require(source.is_dir() and not source.is_symlink(), "SOURCE_TREE_INVALID")
    require(not destination.exists(), "DESTINATION_TREE_EXISTS")
    shutil.copytree(source, destination, symlinks=False)
    for path in destination.rglob("*"):
        if path.is_dir():
            os.chmod(path, 0o700)
        elif path.is_file():
            os.chmod(path, 0o700 if path.name.startswith("run_") else 0o600)


def launcher_source() -> str:
    return f'''#!/usr/bin/env python3
"""Execute the Stage2D9R D2 V3 final host-only read-only preflight once."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import Any

AUTHORIZATION_ID = {AUTHORIZATION_ID!r}
BASELINE_AUTHORIZATION_ID = {BASELINE_AUTHORIZATION_ID!r}
PYTHON_SHA256 = {PYTHON_SHA256!r}
OPENSSL_SHA256 = {OPENSSL_SHA256!r}
REVIEW_ARTIFACT_ID = {REVIEW_ARTIFACT_ID}
REVIEW_ARTIFACT_DIGEST = {REVIEW_ARTIFACT_DIGEST!r}
PUBLIC_PREFLIGHT_ARTIFACT_ID = {PUBLIC_PREFLIGHT_ARTIFACT_ID}
PUBLIC_PREFLIGHT_ARTIFACT_DIGEST = {PUBLIC_PREFLIGHT_ARTIFACT_DIGEST!r}
EXECUTION_PACKAGE_SHA256 = {EXECUTION_PACKAGE_SHA256!r}
EXECUTION_SCRIPT_SHA256 = {EXECUTION_SCRIPT_SHA256!r}
EXECUTION_LAUNCHER_SHA256 = {EXECUTION_LAUNCHER_SHA256!r}
EXECUTION_MARKER_NAME_SHA256 = {EXECUTION_MARKER_NAME_SHA256!r}
LOCKED_RECOVERY_PACKAGE_SHA256 = {LOCKED_RECOVERY_PACKAGE_SHA256!r}
BASELINE_RESULT_SHA256 = {BASELINE_RESULT_SHA256!r}
BOARD_IDENTITY_SHA256 = {BOARD_IDENTITY_SHA256!r}
SERIAL_IDENTITY_SHA256 = {SERIAL_IDENTITY_SHA256!r}
BASELINE_STATE_SHA256 = {BASELINE_STATE_SHA256!r}
TEST_PARTITION_SHA256 = {TEST_PARTITION_SHA256!r}

U1_MARKER = (
    Path.home()
    / ".local/state/greenhouse-stage2d9r/authorizations"
    / "U1-H3N2-STAGE2D9R-SUCCESSOR-PRIVATE-CONTENT-BINDING-20260727-02.consumed.json"
)
BASELINE_RESULT = (
    Path.home()
    / ".local/state/greenhouse-stage2d9r/baseline-readonly-gate-20260727-01/result.json"
)
STATE_ROOT = (
    Path.home()
    / ".local/state/greenhouse-stage2d9r/d2-v3-final-preflight-20260727-01"
)
HOST_PROBE_RESULT = STATE_ROOT / "host-probe-result.json"
PREFLIGHT_OUTPUT = STATE_ROOT / "preflight-result.json"
REQUEST_OUTPUT = STATE_ROOT / "exact-request-draft.json"
RUN_MARKER = STATE_ROOT / "run-marker.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return f"{{stat.S_IMODE(path.stat().st_mode):04o}}"


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def load_json_0600(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    require(file_mode(path) == "0600", code)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), code)
    return value


def write_exclusive(path: Path, value: object) -> None:
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, data.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def verify_manifest(root: Path) -> str:
    manifest = root / "SHA256SUMS"
    require(manifest.is_file() and not manifest.is_symlink(), "MANIFEST_INVALID")
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        if not raw:
            continue
        expected, name = raw.split("  ", 1)
        target = root / name
        require(target.is_file() and not target.is_symlink(), "PACKAGE_MEMBER_INVALID")
        require(sha256_file(target) == expected, "PACKAGE_MEMBER_DIGEST_MISMATCH")
    return sha256_file(manifest)


def validate_frozen_baseline(root: Path) -> None:
    public = json.loads(
        (root / "docs/acceptance/h3-n2-stage2d9r-baseline-readonly-d2-acceptance-20260727-v1.json")
        .read_text(encoding="utf-8")
    )
    private = load_json_0600(BASELINE_RESULT, "BASELINE_RESULT_INVALID")
    expected = {{
        "authorization_id": BASELINE_AUTHORIZATION_ID,
        "status": "CONSUMED_PASS",
        "result_sha256": BASELINE_RESULT_SHA256,
        "board_identity_sha256": BOARD_IDENTITY_SHA256,
        "serial_identity_sha256": SERIAL_IDENTITY_SHA256,
        "baseline_state_sha256": BASELINE_STATE_SHA256,
        "test_partition_sha256": TEST_PARTITION_SHA256,
        "test_partition_size": 65536,
    }}
    for key, value in expected.items():
        require(public.get(key) == value, "PUBLIC_BASELINE_ACCEPTANCE_MISMATCH_" + key.upper())
        require(private.get(key) == value, "PRIVATE_BASELINE_RESULT_MISMATCH_" + key.upper())
    for key in (
        "authorization_consumed", "one_shot",
    ):
        require(private.get(key) is True, "PRIVATE_BASELINE_REQUIRED_TRUE_" + key.upper())
    for key in (
        "replay_permitted", "automatic_retry_permitted",
        "board_write_operation", "flash_erase_operation", "flash_write_operation",
        "flash_verify_operation", "physical_nvs_operation", "network_operation",
        "broker_started", "prepare_executed", "verify_executed",
        "activate_executed", "cleanup_executed", "secret_values_included",
        "private_paths_included",
    ):
        require(private.get(key) is False, "PRIVATE_BASELINE_BOUNDARY_EXPANDED_" + key.upper())


def run_host_probe(root: Path) -> dict[str, Any]:
    probe_root = root / "host-probe-package"
    tool = probe_root / "tools/h3_n2_stage2d9r_successor_host_artifact_custody_probe_20260727_v1.py"
    completed = subprocess.run(
        [sys.executable, str(tool), "--package-root", str(probe_root), "--home", str(Path.home())],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env={{**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}},
    )
    require(completed.returncode == 0, "HOST_PROBE_FAILED")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(lines and lines[0] == "STAGE2D9R_SUCCESSOR_HOST_ARTIFACT_CUSTODY_PREAUTH_PROBE=PASS", "HOST_PROBE_PASS_MARKER_MISSING")
    value = json.loads(lines[-1])
    require(value.get("result") == "PASS_READ_ONLY_PREAUTH", "HOST_PROBE_RESULT_NOT_PASS")
    return value


def main() -> int:
    root = Path(__file__).resolve(strict=True).parent
    try:
        package_sha = verify_manifest(root)
        python_path = Path(sys.executable).resolve(strict=True)
        openssl_name = shutil.which("openssl")
        require(openssl_name is not None, "OPENSSL_UNAVAILABLE")
        openssl_path = Path(openssl_name).resolve(strict=True)
        require(sha256_file(python_path) == PYTHON_SHA256, "PYTHON_EXECUTABLE_SHA_MISMATCH")
        require(sha256_file(openssl_path) == OPENSSL_SHA256, "OPENSSL_EXECUTABLE_SHA_MISMATCH")
        require(U1_MARKER.is_file() and not U1_MARKER.is_symlink(), "U1_CONSUMED_MARKER_MISSING")
        require(file_mode(U1_MARKER) == "0600", "U1_CONSUMED_MARKER_MODE_MISMATCH")
        validate_frozen_baseline(root)

        require(not STATE_ROOT.exists(), "FINAL_PREFLIGHT_STATE_ALREADY_EXISTS")
        STATE_ROOT.mkdir(parents=True, mode=0o700)
        os.chmod(STATE_ROOT, 0o700)
        write_exclusive(
            RUN_MARKER,
            {{
                "schema": "gh.h3.n2.stage2d9r-successor-d2-v3-final-preflight-run-marker/1",
                "authorization_id": AUTHORIZATION_ID,
                "package_sha256": package_sha,
                "authorization_created": False,
                "authorization_claimed": False,
                "board_operation": False,
                "serial_operation": False,
                "flash_operation": False,
                "network_operation": False,
                "automatic_retry_permitted": False,
            }},
        )

        host_probe = run_host_probe(root)
        write_exclusive(HOST_PROBE_RESULT, host_probe)

        issued = datetime.now(timezone.utc).replace(microsecond=0)
        expires = issued + timedelta(seconds=7200)
        issued_at = issued.isoformat().replace("+00:00", "Z")
        expires_at = expires.isoformat().replace("+00:00", "Z")

        command = [
            str(python_path),
            str(root / "tools/h3_n2_stage2d9r_d2_readonly_preflight_v3_20260727.py"),
            "--review-binding", str(root / "inputs/d2-review/D2_REVIEW_BINDING.json"),
            "--repository-state", str(root / "inputs/repository-state.json"),
            "--review-artifact-state", str(root / "inputs/review-artifact-state.json"),
            "--review-artifact-id", str(REVIEW_ARTIFACT_ID),
            "--review-artifact-digest-sha256", REVIEW_ARTIFACT_DIGEST,
            "--public-preflight-artifact-state", str(root / "inputs/public-preflight-artifact-state.json"),
            "--public-preflight-artifact-id", str(PUBLIC_PREFLIGHT_ARTIFACT_ID),
            "--public-preflight-artifact-digest-sha256", PUBLIC_PREFLIGHT_ARTIFACT_DIGEST,
            "--host-probe-result", str(HOST_PROBE_RESULT),
            "--home", str(Path.home()),
            "--u1-02-consumed-marker", str(U1_MARKER),
            "--openssl-executable-sha256", OPENSSL_SHA256,
            "--execution-package-sha256", EXECUTION_PACKAGE_SHA256,
            "--execution-script-sha256", EXECUTION_SCRIPT_SHA256,
            "--execution-launcher-sha256", EXECUTION_LAUNCHER_SHA256,
            "--execution-marker-name-sha256", EXECUTION_MARKER_NAME_SHA256,
            "--locked-recovery-package-sha256", LOCKED_RECOVERY_PACKAGE_SHA256,
            "--recovery-acceptance", str(root / "docs/acceptance/h3-n2-stage2d9r-successor-locked-recovery-artifact-l1-v1.json"),
            "--execution-acceptance", str(root / "docs/acceptance/h3-n2-stage2d9r-successor-d2-execution-package-l1-v1.json"),
            "--recovery-artifact-state", str(root / "inputs/recovery-artifact-state.json"),
            "--execution-artifact-state", str(root / "inputs/execution-artifact-state.json"),
            "--baseline-readonly-result", str(BASELINE_RESULT),
            "--issued-at", issued_at,
            "--expires-at", expires_at,
            "--preflight-output", str(PREFLIGHT_OUTPUT),
            "--request-output", str(REQUEST_OUTPUT),
        ]
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env={{**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}},
        )
        require(completed.returncode == 0, "V3_FINAL_PREFLIGHT_FAILED")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        require(lines, "V3_FINAL_PREFLIGHT_OUTPUT_MISSING")
        result = json.loads(lines[-1])
        require(result.get("status") == "PASS", "V3_FINAL_PREFLIGHT_NOT_PASS")
        require(result.get("authorized") is False, "V3_FINAL_PREFLIGHT_AUTHORIZATION_EXPANDED")
        require(PREFLIGHT_OUTPUT.is_file() and REQUEST_OUTPUT.is_file(), "V3_FINAL_PREFLIGHT_OUTPUT_FILES_MISSING")
        request = json.loads(REQUEST_OUTPUT.read_text(encoding="utf-8"))
        require(request.get("authorized") is False, "EXACT_REQUEST_DRAFT_AUTHORIZED")
        print(json.dumps({{
            **result,
            "status": "PASS",
            "state": "D2_V3_FINAL_PREFLIGHT_PASS_UNAUTHORIZED_REQUEST_DRAFT",
            "authorization_id": AUTHORIZATION_ID,
            "authorization_created": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "request_authorized": False,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "host_probe_result_sha256": sha256_file(HOST_PROBE_RESULT),
            "preflight_output_sha256": sha256_file(PREFLIGHT_OUTPUT),
            "request_output_sha256": sha256_file(REQUEST_OUTPUT),
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "physical_nvs_operation": False,
            "network_operation": False,
            "broker_started": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "automatic_retry_permitted": False,
            "replay_permitted": False,
            "private_paths_included": False,
            "secret_values_included": False,
        }}, sort_keys=True))
        return 0
    except Exception as exc:
        code = str(exc.args[0]) if getattr(exc, "args", None) else type(exc).__name__
        print(json.dumps({{
            "status": "FAIL_CLOSED",
            "failure_code": code,
            "authorization_id": AUTHORIZATION_ID,
            "authorization_created": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "request_authorized": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "physical_nvs_operation": False,
            "network_operation": False,
            "broker_started": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "automatic_retry_permitted": False,
            "replay_permitted": False,
            "private_paths_included": False,
            "secret_values_included": False,
        }}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)

    for relative in REPOSITORY_FILES:
        copy_regular(ROOT / relative, output / relative)

    copy_tree(args.d2_review, output / "inputs/d2-review")
    copy_tree(args.public_preflight, output / "inputs/public-preflight")
    copy_tree(args.host_probe_package, output / "host-probe-package")
    copy_tree(args.baseline_acceptance_artifact, output / "inputs/baseline-acceptance-artifact")

    for name, source in (
        ("repository-state.json", args.repository_state),
        ("review-artifact-state.json", args.review_artifact_state),
        ("public-preflight-artifact-state.json", args.public_preflight_artifact_state),
        ("recovery-artifact-state.json", args.recovery_artifact_state),
        ("execution-artifact-state.json", args.execution_artifact_state),
    ):
        copy_regular(source, output / "inputs" / name)

    launcher = output / "run_stage2d9r_successor_d2_v3_final_preflight_host_readonly_20260727_v1.py"
    launcher.write_text(launcher_source(), encoding="utf-8")
    os.chmod(launcher, 0o700)

    shell = output / "run_stage2d9r_successor_d2_v3_final_preflight_host_readonly_20260727_v1.sh"
    shell.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "umask 077\n"
        "ROOT=\"$(CDPATH= cd -- \"$(dirname -- \"$0\")\" && pwd -P)\"\n"
        "export PYTHONDONTWRITEBYTECODE=1\n"
        "exec python3 \"$ROOT/run_stage2d9r_successor_d2_v3_final_preflight_host_readonly_20260727_v1.py\"\n",
        encoding="utf-8",
    )
    os.chmod(shell, 0o700)

    binding: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-successor-d2-v3-final-preflight-host-package/1",
        "stage": "H3/N2 Stage 2D-9R G3R successor",
        "state": "HOST_ONLY_FINAL_PREFLIGHT_PACKAGE_FROZEN",
        "repository": "chrenguo-stack/HomeAssistant",
        "package_source_sha": args.source_sha,
        "layered_base_sha": SOURCE_BASE_SHA,
        "pr180_sha": PR180_SHA,
        "pr176_sha": PR176_SHA,
        "main_sha": MAIN_SHA,
        "d2_request_id": AUTHORIZATION_ID,
        "baseline_authorization_id": BASELINE_AUTHORIZATION_ID,
        "review_artifact": {
            "id": REVIEW_ARTIFACT_ID,
            "digest_sha256": REVIEW_ARTIFACT_DIGEST,
            "source_sha": PR180_SHA,
        },
        "public_preflight_artifact": {
            "id": PUBLIC_PREFLIGHT_ARTIFACT_ID,
            "digest_sha256": PUBLIC_PREFLIGHT_ARTIFACT_DIGEST,
            "source_sha": PR180_SHA,
        },
        "recovery_artifact": {
            "id": RECOVERY_ARTIFACT_ID,
            "digest_sha256": RECOVERY_ARTIFACT_DIGEST,
            "source_sha": RECOVERY_SOURCE_SHA,
        },
        "execution_artifact": {
            "id": EXECUTION_ARTIFACT_ID,
            "digest_sha256": EXECUTION_ARTIFACT_DIGEST,
            "source_sha": EXECUTION_SOURCE_SHA,
        },
        "host_probe_artifact": {
            "id": HOST_PROBE_ARTIFACT_ID,
            "digest_sha256": HOST_PROBE_ARTIFACT_DIGEST,
            "source_sha": PR180_SHA,
        },
        "baseline_acceptance_artifact": {
            "id": BASELINE_ACCEPTANCE_ARTIFACT_ID,
            "digest_sha256": BASELINE_ACCEPTANCE_ARTIFACT_DIGEST,
            "source_sha": SOURCE_BASE_SHA,
        },
        "python_executable_sha256": PYTHON_SHA256,
        "openssl_executable_sha256": OPENSSL_SHA256,
        "baseline_result_sha256": BASELINE_RESULT_SHA256,
        "board_identity_sha256": BOARD_IDENTITY_SHA256,
        "serial_identity_sha256": SERIAL_IDENTITY_SHA256,
        "baseline_state_sha256": BASELINE_STATE_SHA256,
        "test_partition_sha256": TEST_PARTITION_SHA256,
        "artifact_state_inputs_frozen": True,
        "host_probe_reexecuted_read_only": True,
        "marker_only_consumed_evidence": True,
        "exact_request_draft_generated": True,
        "exact_request_authorized": False,
        "authorization_record_included": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "operator_host_network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
        "ready_authorized": False,
        "merge_authorized": False,
        "release_authorized": False,
        "tag_authorized": False,
        "deployment_authorized": False,
    }
    binding["binding_sha256"] = canonical_sha256(binding)
    binding_path = output / "D2_V3_FINAL_PREFLIGHT_PACKAGE_BINDING.json"
    binding_path.write_text(
        json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.chmod(binding_path, 0o600)

    readme = output / "README.md"
    readme.write_text(
        "# Stage2D9R D2 V3 最终预检（无板卡、纯主机只读）\n\n"
        "该包重新执行只读 Host Artifact/私密托管元数据探针，验证 U1 consumed marker、"
        "已消费板卡基线结果、冻结的 V2 Review/Public Preflight、恢复包与执行包绑定，"
        "并生成 `authorized=false` 的精确 D2 请求草案。\n\n"
        "操作主机不得连接测试板；运行过程不枚举 USB/串口，不访问 Flash/NVS，"
        "不连接网络或 Broker，不执行 PREPARE、VERIFY、ACTIVATE、CLEANUP。\n\n"
        "该启动器只允许运行一次。成功或失败后均不要自行删除状态目录或重试，"
        "请返回终端最后一行 JSON。\n",
        encoding="utf-8",
    )
    os.chmod(readme, 0o600)

    sums: list[str] = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(f"{sha256_file(path)}  {path.relative_to(output)}")
    manifest = output / "SHA256SUMS"
    manifest.write_text("\n".join(sums) + "\n", encoding="utf-8")
    os.chmod(manifest, 0o600)
    return binding


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--source-sha", required=True)
    value.add_argument("--d2-review", type=Path, required=True)
    value.add_argument("--public-preflight", type=Path, required=True)
    value.add_argument("--host-probe-package", type=Path, required=True)
    value.add_argument("--baseline-acceptance-artifact", type=Path, required=True)
    value.add_argument("--repository-state", type=Path, required=True)
    value.add_argument("--review-artifact-state", type=Path, required=True)
    value.add_argument("--public-preflight-artifact-state", type=Path, required=True)
    value.add_argument("--recovery-artifact-state", type=Path, required=True)
    value.add_argument("--execution-artifact-state", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        binding = build(args)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, PackageError) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "PASS",
        "binding_sha256": binding["binding_sha256"],
        "exact_request_authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
