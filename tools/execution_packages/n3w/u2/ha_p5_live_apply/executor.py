#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
STORAGE_POLICY_PATH = REPO_ROOT / "infra/n3w-t1/upgrades/homeassistant-2026.10.4-storage-policy.json"
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

import n3w_t1_fresh_product_staging_host as staging_host

REPOSITORY = "chrenguo-stack/HomeAssistant"
GATE_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_LIVE_APPLY_PREAUTHORIZATION_REVIEW_20261105_01"
SCHEMA = "gh.n3w-t1-core-updater-ha-p5-live-apply-execution/1"
REMOTE_SCHEMA = "gh.n3w-t1-core-updater-ha-p5-live/1"

AUTHORIZATION_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_LIVE_APPLY_P5_20261105_01"
CONFIRMATION = "EXECUTE HA P5 LIVE APPLY: YES"

RUN_ID = 41976542377
ARTIFACT_ID = 13391983948
ARTIFACT_NAME = "n3w-t1-core-updater-homeassistant-2026.10.4-arm64-fb7cfc857003ace3d368521d76ca2320ba399736"
ARTIFACT_DIGEST = "sha256:df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2"
ARTIFACT_HEAD = "fb7cfc857003ace3d368521d76ca2320ba399736"
ARCHIVE_NAME = "homeassistant-arm64.tar.gz"
ARCHIVE_SHA256 = "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
ARCHIVE_SIZE_BYTES = 835309535
TARGET_IMAGE = "local/n3w-homeassistant:2026.10.4-5881590f"
PREDECESSOR_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
P4_BASELINE_SHA256 = "78c3b0b58ad39cf887689658bec90c8466d30a93d58830b0289f1463dafad868"
P4_TRANSACTION_SHA256 = "6ad39528f43407c6f48b83a07cb2d4ddfc916e808b3957aae176608c89a98fa3"
P5_POST_PEAK_RESERVE_BYTES = 1610612736
STORAGE_POLICY_EVIDENCE_HEAD = "9cf4fcee9512013ca99675b3b477cf77429bd669"

EXPECTED_ARTIFACT_FILES = {
    "homeassistant-arm64.tar.gz",
    "portable-image-identity.json",
    "upstream-binding.json",
}
LOCAL_AUTHORITY_PATHS = (
    "tools/n3w_t1_fresh_product_staging_host.py",
    "infra/n3w-t1/upgrades/homeassistant-2026.10.4-storage-policy.json",
)
SOURCE_PATHS = (
    "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json",
    "tools/n3w_t1_core_updater_common.py",
    "tools/n3w_t1_core_updater_core.py",
    "tools/n3w_t1_core_updater_host.py",
    "tools/n3w_t1_core_updater_state.py",
    "tools/n3w_t1_core_updater_a1_policy.py",
    "tools/n3w_t1_core_updater_components.py",
    "tools/n3w_t1_core_updater_v2.py",
    "tools/n3w_t1_core_updater_v2_common.py",
    "tools/n3w_t1_core_updater_v2_state.py",
    "tools/n3w_t1_portable_image_identity.py",
    "tools/execution_packages/n3w/u2/ha_p5_live_apply/remote_live.py",
)
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")

REMOTE_EXTRACT = r"""
import os
import sys
import tarfile

archive_path = sys.argv[1]
destination = sys.argv[2]
with tarfile.open(archive_path, mode="r:*") as archive:
    members = archive.getmembers()
    for member in members:
        if (
            member.name.startswith("/")
            or ".." in member.name.split("/")
            or "/" in member.name
            or member.issym()
            or member.islnk()
        ):
            raise SystemExit(23)
    archive.extractall(destination)
for name in os.listdir(destination):
    path = os.path.join(destination, name)
    if os.path.isfile(path):
        os.chmod(path, 0o600)
"""


class StopExecution(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(
    argv: list[str],
    *,
    timeout: int = 180,
    check: bool = True,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            argv,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise StopExecution(f"command_timeout:{Path(argv[0]).name}") from error
    except OSError as error:
        raise StopExecution(f"command_transport_error:{Path(argv[0]).name}") from error
    if check and result.returncode != 0:
        raise StopExecution(f"command_failed:{Path(argv[0]).name}:{result.returncode}")
    return result


def git_text(*args: str) -> str:
    return run(["git", "-C", str(REPO_ROOT), *args], timeout=30).stdout.decode().strip()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution(f"json_invalid:{path.name}") from error
    if not isinstance(value, dict):
        raise StopExecution(f"json_shape_invalid:{path.name}")
    return value


def validate_storage_policy() -> dict[str, Any]:
    policy = read_json(STORAGE_POLICY_PATH)
    if (
        policy.get("schema")
        != "gh.n3w-t1-core-updater-homeassistant-storage-policy/1"
        or policy.get("component") != "homeassistant"
        or policy.get("target_image") != TARGET_IMAGE
        or policy.get("target_manifest_blob_sha")
        != "6966b4fe4d7620ccc436643cc840da9ae95e6010"
        or policy.get("evidence_source_head") != STORAGE_POLICY_EVIDENCE_HEAD
        or policy.get("live_ha_apply_authorized") is not False
    ):
        raise StopExecution("storage_policy_authority_invalid")
    admission = policy.get("p5_upgrade_admission")
    if not isinstance(admission, dict):
        raise StopExecution("storage_policy_admission_invalid")
    if (
        admission.get("historical_fixed_5_gib_retired") is not True
        or admission.get("derived_post_peak_reserve_bytes")
        != P5_POST_PEAK_RESERVE_BYTES
        or admission.get("exact_target_archive_staging_bytes")
        != ARCHIVE_SIZE_BYTES
        or admission.get("rollback_predecessor_already_resident") is not True
        or admission.get("predecessor_bytes_double_counted") is not False
    ):
        raise StopExecution("storage_policy_admission_invalid")
    runtime = policy.get("product_runtime_min_free_requirement")
    if (
        not isinstance(runtime, dict)
        or runtime.get("state")
        != "UNFROZEN_LONGITUDINAL_EVIDENCE_REQUIRED"
    ):
        raise StopExecution("storage_policy_runtime_state_invalid")
    return policy


def validate_target(target: str) -> None:
    if (
        not target
        or target.strip() != target
        or any(character.isspace() for character in target)
        or target.startswith("-")
        or any(mark in target.casefold() for mark in ("placeholder", "example", "<", ">"))
    ):
        raise StopExecution("t1_target_invalid")


def validate_source(expected_head: str) -> dict[str, Any]:
    if GIT_SHA.fullmatch(expected_head) is None:
        raise StopExecution("expected_source_head_invalid")
    if git_text("rev-parse", "HEAD") != expected_head:
        raise StopExecution("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("tracked_worktree_dirty")

    manifest = read_json(MANIFEST_PATH)
    if manifest.get("schema") != "gh.n3w-t1-core-updater-ha-p5-live-apply-execution-package/1":
        raise StopExecution("manifest_schema_invalid")
    if manifest.get("gate_id") != GATE_ID:
        raise StopExecution("manifest_gate_invalid")
    if manifest.get("authority_parent_head") != "d6b6d0f89837a85d94d60b4df45ab9eb4000d764":
        raise StopExecution("authority_parent_invalid")
    if manifest.get("p4_execution_head") != "8232707eb2c91d3fa9881e4cadba6b78eefc1494":
        raise StopExecution("p4_execution_authority_invalid")
    if manifest.get("p4_baseline_sha256") != P4_BASELINE_SHA256:
        raise StopExecution("p4_baseline_authority_invalid")
    if manifest.get("p4_transaction_sha256") != P4_TRANSACTION_SHA256:
        raise StopExecution("p4_transaction_authority_invalid")
    if manifest.get("proposed_authorization_id") != AUTHORIZATION_ID:
        raise StopExecution("authorization_id_manifest_mismatch")
    live_authorized = manifest.get("live_apply_authorized")
    if not isinstance(live_authorized, bool):
        raise StopExecution("manifest_live_authorization_invalid")

    ancestor = run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "merge-base",
            "--is-ancestor",
            manifest["authority_parent_head"],
            expected_head,
        ],
        timeout=30,
        check=False,
    )
    if ancestor.returncode != 0:
        raise StopExecution("authority_parent_not_ancestor")

    bindings = manifest.get("source_binding")
    if not isinstance(bindings, dict):
        raise StopExecution("manifest_source_binding_invalid")
    for relative, expected_blob in bindings.items():
        if not isinstance(relative, str) or not isinstance(expected_blob, str):
            raise StopExecution("manifest_source_binding_invalid")
        if GIT_SHA.fullmatch(expected_blob) is None:
            raise StopExecution("manifest_source_blob_invalid")
        if git_text("rev-parse", f"{expected_head}:{relative}") != expected_blob:
            raise StopExecution(f"source_blob_mismatch:{Path(relative).name}")

    for relative in (*SOURCE_PATHS, *LOCAL_AUTHORITY_PATHS):
        if relative not in bindings:
            raise StopExecution(f"source_binding_missing:{Path(relative).name}")

    validate_storage_policy()

    target_blob = bindings.get("infra/n3w-t1/upgrades/homeassistant-2026.10.4.json")
    if target_blob != "6966b4fe4d7620ccc436643cc840da9ae95e6010":
        raise StopExecution("target_blob_drift")

    return {
        "exact_source_head": expected_head,
        "authority_parent_head": manifest["authority_parent_head"],
        "p4_execution_head": manifest["p4_execution_head"],
        "p4_closure_blob_sha": manifest["p4_closure_blob_sha"],
        "target_manifest_blob_sha": target_blob,
        "live_apply_authorized": live_authorized,
        "storage_policy_blob_sha": bindings[
            "infra/n3w-t1/upgrades/homeassistant-2026.10.4-storage-policy.json"
        ],
    }


def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    repo = REPO_ROOT.resolve()
    if root == repo or repo in root.parents:
        raise StopExecution("evidence_root_inside_repository")
    if root.exists():
        if (
            root.is_symlink()
            or not root.is_dir()
            or root.stat().st_uid != os.geteuid()
            or stat.S_IMODE(root.stat().st_mode) != 0o700
            or any(root.iterdir())
        ):
            raise StopExecution("evidence_root_invalid")
    else:
        root.mkdir(parents=True, mode=0o700)
    return root


def write_private(path: Path, value: Any) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise StopExecution("evidence_write_short")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def verify_artifact(download_root: Path) -> tuple[Path, dict[str, Any]]:
    metadata_raw = run(
        ["gh", "api", f"repos/{REPOSITORY}/actions/artifacts/{ARTIFACT_ID}"],
        timeout=60,
    ).stdout
    try:
        metadata = json.loads(metadata_raw)
    except json.JSONDecodeError as error:
        raise StopExecution("artifact_metadata_invalid") from error
    if (
        metadata.get("id") != ARTIFACT_ID
        or metadata.get("name") != ARTIFACT_NAME
        or metadata.get("digest") != ARTIFACT_DIGEST
        or metadata.get("expired") is not False
        or metadata.get("workflow_run", {}).get("id") != RUN_ID
        or metadata.get("workflow_run", {}).get("head_sha") != ARTIFACT_HEAD
    ):
        raise StopExecution("artifact_metadata_mismatch")

    package = download_root / "artifact"
    package.mkdir()
    run(
        [
            "gh",
            "run",
            "download",
            str(RUN_ID),
            "-R",
            REPOSITORY,
            "-n",
            ARTIFACT_NAME,
            "-D",
            str(package),
        ],
        timeout=1800,
    )
    observed = {item.name for item in package.iterdir()}
    if observed != EXPECTED_ARTIFACT_FILES:
        raise StopExecution("artifact_file_set_mismatch")

    archive = package / ARCHIVE_NAME
    if archive.stat().st_size != ARCHIVE_SIZE_BYTES:
        raise StopExecution("archive_size_mismatch")
    if sha256_file(archive) != ARCHIVE_SHA256:
        raise StopExecution("archive_sha256_mismatch")
    try:
        with tarfile.open(archive, mode="r:*") as docker_save:
            image_uncompressed_bytes = sum(
                member.size for member in docker_save.getmembers() if member.isfile()
            )
    except tarfile.TarError as error:
        raise StopExecution("archive_tar_invalid") from error
    if image_uncompressed_bytes <= 0:
        raise StopExecution("archive_uncompressed_size_invalid")

    target = read_json(REPO_ROOT / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json")
    binding = read_json(package / "upstream-binding.json")
    portable = read_json(package / "portable-image-identity.json")
    if (
        target.get("component") != "homeassistant"
        or target.get("target_image_ref") != TARGET_IMAGE
        or target.get("expected_predecessor_image_ref") != PREDECESSOR_IMAGE
        or target.get("target_archive_sha256") != ARCHIVE_SHA256
        or target.get("artifact_identity", {}).get("artifact_id") != ARTIFACT_ID
        or target.get("artifact_identity", {}).get("artifact_digest_sha256")
        != ARTIFACT_DIGEST.removeprefix("sha256:")
    ):
        raise StopExecution("target_artifact_binding_invalid")
    if (
        binding.get("schema") != "gh.n3w-t1-core-updater-homeassistant-upstream-artifact/1"
        or binding.get("control_plane_head") != ARTIFACT_HEAD
        or binding.get("component") != "homeassistant"
        or binding.get("version") != "2026.10.4"
        or binding.get("platform") != "linux/arm64"
        or binding.get("local_image") != TARGET_IMAGE
        or binding.get("archive_sha256") != ARCHIVE_SHA256
        or binding.get("archive_size_bytes") != ARCHIVE_SIZE_BYTES
        or binding.get("secret_values_included") is not False
        or binding.get("t1_mutation") is not False
    ):
        raise StopExecution("upstream_binding_invalid")
    if (
        portable.get("archive_sha256") != ARCHIVE_SHA256
        or portable.get("archive_size_bytes") != ARCHIVE_SIZE_BYTES
        or portable.get("os") != "linux"
        or portable.get("architecture") != "arm64"
    ):
        raise StopExecution("portable_identity_invalid")

    return archive, {
        "artifact_id": metadata["id"],
        "artifact_name": metadata["name"],
        "artifact_digest": metadata["digest"],
        "artifact_source_head": metadata["workflow_run"]["head_sha"],
        "archive_sha256": ARCHIVE_SHA256,
        "archive_size_bytes": ARCHIVE_SIZE_BYTES,
        "image_uncompressed_bytes": image_uncompressed_bytes,
        "target_image": TARGET_IMAGE,
    }


def build_source_bundle(path: Path) -> None:
    with tarfile.open(path, mode="w") as archive:
        for relative in SOURCE_PATHS:
            source = REPO_ROOT / relative
            if source.is_symlink() or not source.is_file():
                raise StopExecution(f"source_file_invalid:{Path(relative).name}")
            if relative.endswith("homeassistant-2026.10.4.json"):
                name = "target.json"
            elif relative.endswith("remote_live.py"):
                name = "remote_live.py"
            else:
                name = Path(relative).name
            payload = source.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))


def ssh_options(control_path: str) -> list[str]:
    return [
        "-o",
        "ControlMaster=auto",
        "-o",
        f"ControlPath={control_path}",
        "-o",
        "ControlPersist=600",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=2",
        "-o",
        "PreferredAuthentications=publickey,password",
        "-o",
        "NumberOfPasswordPrompts=1",
    ]


def ssh_command(
    target: str,
    control_path: str,
    command: str,
    *,
    timeout: int = 180,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    validate_target(target)
    return run(
        ["ssh", *ssh_options(control_path), target, command],
        timeout=timeout,
        check=check,
    )


def scp_file(
    source: Path,
    target: str,
    remote_path: str,
    control_path: str,
    *,
    timeout: int,
) -> None:
    validate_target(target)
    run(
        [
            "scp",
            "-q",
            *ssh_options(control_path),
            str(source),
            f"{target}:{remote_path}",
        ],
        timeout=timeout,
    )


def parse_remote_json(result: subprocess.CompletedProcess[bytes], operation: str) -> dict[str, Any]:
    try:
        value = json.loads(result.stdout.decode())
    except (UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution(f"{operation}_json_invalid") from error
    if not isinstance(value, dict):
        raise StopExecution(f"{operation}_json_shape_invalid")
    return value


def run_remote_live(
    target: str,
    control_path: str,
    remote_dir: str,
    operation: str,
    *,
    authorization_id: str | None = None,
    timeout: int = 300,
) -> tuple[dict[str, Any], int]:
    command = [
        "cd",
        remote_dir,
        "&&",
        "sudo",
        "-n",
        "python3",
        "-B",
        "remote_live.py",
        operation,
    ]
    if operation in {"preflight", "apply"}:
        command.extend(["--image-tar", ARCHIVE_NAME])
    if operation == "apply":
        if authorization_id is None:
            raise StopExecution("authorization_id_required")
        command.extend(["--authorization-id", authorization_id])
    raw = " ".join(shlex.quote(item) if item != "&&" else item for item in command)
    result = ssh_command(
        target,
        control_path,
        raw,
        timeout=timeout,
        check=False,
    )
    if result.returncode not in (0, 2):
        raise StopExecution(f"{operation}_transport_exit:{result.returncode}")
    return parse_remote_json(result, operation), result.returncode


def require_preflight_pass(document: dict[str, Any]) -> None:
    if (
        document.get("schema") != REMOTE_SCHEMA
        or document.get("status") != "PASS"
        or document.get("operation") != "preflight"
        or document.get("mutation") is not False
        or document.get("authorization_claimed") is not False
        or document.get("authorization_consumed") is not False
        or document.get("runtime_class") != "TARGET_BOUND_RUNNING"
        or document.get("health_state") != "HEALTHY"
        or document.get("recovery_required") is not False
        or document.get("baseline_double_read_stable") is not True
        or document.get("baseline_sha256") != P4_BASELINE_SHA256
        or document.get("transaction_sha256") != P4_TRANSACTION_SHA256
        or document.get("target_image_prestate") != "ABSENT"
        or document.get("target_archive_verified") is not True
        or document.get("template_convergence_planned") is not True
        or document.get("rollback_available") is not True
    ):
        raise StopExecution("live_preflight_contract_invalid")
    plan_sha = document.get("plan_sha256")
    if not isinstance(plan_sha, str) or SHA256.fullmatch(plan_sha) is None:
        raise StopExecution("live_preflight_plan_sha_invalid")


def require_apply_pass(document: dict[str, Any]) -> None:
    if (
        document.get("status") != "PASS"
        or document.get("operation") != "apply"
        or document.get("component") != "homeassistant"
        or document.get("transaction_status") != "COMMITTED"
        or document.get("authorization_consumed") is not True
        or document.get("t1_mutation") is not True
    ):
        raise StopExecution("live_apply_contract_invalid")


def require_post_pass(document: dict[str, Any]) -> None:
    if (
        document.get("schema") != REMOTE_SCHEMA
        or document.get("status") != "PASS"
        or document.get("operation") != "post"
        or document.get("mutation") is not False
        or document.get("recovery_required") is not False
        or document.get("runtime_class") != "TARGET_BOUND_RUNNING"
        or document.get("health_state") != "HEALTHY"
        or document.get("image_bindings")
        != {
            "manager": "local/greenhouse-manager:fresh-5b32e1ae8210",
            "homeassistant": TARGET_IMAGE,
            "broker": "local/n3w-mosquitto:2.1.2-3184566d",
        }
        or document.get("image_binding_modes")
        != {
            "manager": "dynamic",
            "homeassistant": "dynamic",
            "broker": "legacy_static",
        }
        or document.get("manager_mqtt_authenticated") is not True
        or document.get("homeassistant_mqtt_authenticated") is not True
        or document.get("homeassistant_http_status") not in {200, 401}
        or document.get("listeners")
        != {
            "tcp_8883": 1,
            "tcp_47110": 1,
            "udp_47111": 1,
            "tcp_47112": 0,
        }
    ):
        raise StopExecution("live_post_contract_invalid")
    tx_sha = document.get("transaction_sha256")
    if not isinstance(tx_sha, str) or SHA256.fullmatch(tx_sha) is None:
        raise StopExecution("live_post_transaction_sha_invalid")


def remote_storage_report(
    target: str,
    control_path: str,
) -> dict[str, Any]:
    script = staging_host._remote_storage_probe_script()
    result = ssh_command(
        target,
        control_path,
        "python3 -c " + shlex.quote(script),
        timeout=90,
    )
    try:
        report = json.loads(result.stdout.decode())
    except (UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution("remote_storage_report_invalid") from error
    if not isinstance(report, dict):
        raise StopExecution("remote_storage_report_invalid")
    if report.get("staging_root") != "/var/tmp":
        raise StopExecution("remote_staging_root_invalid")
    if report.get("staging_fstype") in {"tmpfs", "ramfs"}:
        raise StopExecution("remote_staging_root_memory_fs")
    if report.get("image_store_backend") not in {"classic", "containerd"}:
        raise StopExecution("remote_image_store_unresolved")
    if not (
        report.get("staging_device")
        == report.get("docker_device")
        == report.get("image_store_device")
    ):
        raise StopExecution("remote_storage_filesystem_split_unsupported")
    for key in ("staging_free_bytes", "docker_free_bytes", "image_store_free_bytes"):
        value = report.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise StopExecution("remote_free_bytes_invalid")
    return report


def capacity_report(
    artifact: dict[str, Any],
    storage: dict[str, Any],
) -> dict[str, Any]:
    policy = validate_storage_policy()
    admission = policy["p5_upgrade_admission"]
    image_uncompressed = artifact.get("image_uncompressed_bytes")
    if not isinstance(image_uncompressed, int) or image_uncompressed <= 0:
        raise StopExecution("image_uncompressed_bytes_invalid")
    free = min(
        int(storage["staging_free_bytes"]),
        int(storage["docker_free_bytes"]),
        int(storage["image_store_free_bytes"]),
    )
    required_peak = ARCHIVE_SIZE_BYTES + image_uncompressed
    required_total = required_peak + P5_POST_PEAK_RESERVE_BYTES
    report = {
        "staging_device": storage["staging_device"],
        "docker_device": storage["docker_device"],
        "image_store_device": storage["image_store_device"],
        "image_store_backend": storage["image_store_backend"],
        "image_store_root_source": storage.get("image_store_root_source"),
        "remote_free_bytes": free,
        "archive_size_bytes": ARCHIVE_SIZE_BYTES,
        "image_uncompressed_bytes": image_uncompressed,
        "required_peak_bytes": required_peak,
        "post_peak_reserve_bytes": P5_POST_PEAK_RESERVE_BYTES,
        "required_total_bytes": required_total,
        "capacity_pass": free >= required_total,
        "storage_policy_evidence_head": policy["evidence_source_head"],
        "historical_fixed_5_gib_retired": admission[
            "historical_fixed_5_gib_retired"
        ],
        "rollback_predecessor_already_resident": admission[
            "rollback_predecessor_already_resident"
        ],
        "predecessor_bytes_double_counted": admission[
            "predecessor_bytes_double_counted"
        ],
        "product_runtime_min_free_requirement_state": policy[
            "product_runtime_min_free_requirement"
        ]["state"],
    }
    if report["capacity_pass"] is not True:
        raise StopExecution("remote_capacity_insufficient")
    return report


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.authorization_id != AUTHORIZATION_ID:
        raise StopExecution("authorization_id_invalid")
    if args.confirm != CONFIRMATION:
        raise StopExecution("live_confirmation_invalid")
    validate_target(args.target)
    source_authority = validate_source(args.expected_source_head)
    if source_authority.get("live_apply_authorized") is not True:
        raise StopExecution("live_apply_not_authorized")
    validate_storage_policy()
    evidence = prepare_evidence_root(args.evidence_root)

    remote_dir: str | None = None
    control_path = f"/tmp/n3w-ha-p5-{os.getpid()}.sock"
    remote_scratch_cleanup = False
    final_result: dict[str, Any] | None = None

    with tempfile.TemporaryDirectory(prefix="n3w-ha-p5-local-") as raw_tmp:
        temp_root = Path(raw_tmp)
        archive, artifact = verify_artifact(temp_root)
        write_private(evidence / "artifact.json", artifact)
        bundle = temp_root / "source-bundle.tar"
        build_source_bundle(bundle)

        try:
            master = ssh_command(args.target, control_path, "true", timeout=30)
            if master.returncode != 0:
                raise StopExecution("ssh_master_start_failed")

            storage = remote_storage_report(args.target, control_path)
            capacity = capacity_report(artifact, storage)
            write_private(evidence / "capacity.json", capacity)

            created = ssh_command(
                args.target,
                control_path,
                "mktemp -d /var/tmp/n3w-ha-p5.XXXXXX",
                timeout=30,
            )
            remote_dir = created.stdout.decode().strip()
            if not re.fullmatch(r"/var/tmp/n3w-ha-p5\.[A-Za-z0-9]+", remote_dir):
                raise StopExecution("remote_dir_invalid")
            ssh_command(
                args.target,
                control_path,
                f"chmod 700 {shlex.quote(remote_dir)}",
                timeout=30,
            )

            scp_file(
                bundle,
                args.target,
                f"{remote_dir}/source-bundle.tar",
                control_path,
                timeout=120,
            )
            scp_file(
                archive,
                args.target,
                f"{remote_dir}/{ARCHIVE_NAME}",
                control_path,
                timeout=1800,
            )

            extract_command = " ".join(
                [
                    "sudo",
                    "-n",
                    "python3",
                    "-c",
                    shlex.quote(REMOTE_EXTRACT),
                    shlex.quote(f"{remote_dir}/source-bundle.tar"),
                    shlex.quote(remote_dir),
                ]
            )
            ssh_command(args.target, control_path, extract_command, timeout=120)
            ssh_command(
                args.target,
                control_path,
                f"rm -f {shlex.quote(remote_dir + '/source-bundle.tar')}",
                timeout=30,
            )

            preflight, pre_rc = run_remote_live(
                args.target,
                control_path,
                remote_dir,
                "preflight",
                timeout=600,
            )
            write_private(evidence / "preflight.json", preflight)
            if pre_rc != 0 or preflight.get("status") != "PASS":
                raise StopExecution(
                    "live_preflight_stop:" + str(preflight.get("reason") or "unknown")
                )
            require_preflight_pass(preflight)

            claim = {
                "authorization_id": AUTHORIZATION_ID,
                "authorization_claimed": True,
                "authorization_consumed_by_executor": True,
                "replay_permitted": False,
                "permitted_apply_invocations": 1,
                "reason": "single Home Assistant P5 live apply invocation begins",
            }
            write_private(evidence / "authorization-claim.json", claim)

            apply_report, apply_rc = run_remote_live(
                args.target,
                control_path,
                remote_dir,
                "apply",
                authorization_id=AUTHORIZATION_ID,
                timeout=1800,
            )
            write_private(evidence / "apply.json", apply_report)

            if apply_rc != 0 or apply_report.get("status") != "PASS":
                diagnose, _ = run_remote_live(
                    args.target,
                    control_path,
                    remote_dir,
                    "diagnose",
                    timeout=300,
                )
                write_private(evidence / "diagnose.json", diagnose)
                raise StopExecution(
                    "live_apply_stop:" + str(apply_report.get("reason") or "unknown")
                )

            require_apply_pass(apply_report)

            post, post_rc = run_remote_live(
                args.target,
                control_path,
                remote_dir,
                "post",
                timeout=600,
            )
            write_private(evidence / "post.json", post)
            if post_rc != 0 or post.get("status") != "PASS":
                raise StopExecution(
                    "live_post_stop:" + str(post.get("reason") or "unknown")
                )
            require_post_pass(post)

            final_result = {
                "schema": SCHEMA,
                "gate_id": GATE_ID,
                "status": "PASS",
                "operation": "live_apply",
                "source_authority": source_authority,
                "artifact": artifact,
                "capacity": capacity,
                "authorization_id": AUTHORIZATION_ID,
                "authorization_claimed": True,
                "authorization_consumed": True,
                "authorization_replay_permitted": False,
                "apply_invocation_count": 1,
                "apply_status": "PASS",
                "apply_transaction_status": "COMMITTED",
                "apply_t1_mutation": True,
                "post_recovery_required": post["recovery_required"],
                "post_runtime_class": post["runtime_class"],
                "post_health_state": post["health_state"],
                "post_image_bindings": post["image_bindings"],
                "post_image_binding_modes": post["image_binding_modes"],
                "post_transaction_sha256": post["transaction_sha256"],
                "manager_mqtt_authenticated": post["manager_mqtt_authenticated"],
                "homeassistant_mqtt_authenticated": post["homeassistant_mqtt_authenticated"],
                "homeassistant_http_status": post["homeassistant_http_status"],
                "listeners": post["listeners"],
                "second_apply_allowed": False,
                "blind_explicit_rollback_allowed": False,
                "board_access": False,
                "merge": False,
                "private_evidence_files": [
                    "artifact.json",
                    "capacity.json",
                    "preflight.json",
                    "authorization-claim.json",
                    "apply.json",
                    "post.json",
                ],
            }
        finally:
            if remote_dir is not None:
                cleanup = ssh_command(
                    args.target,
                    control_path,
                    f"rm -rf {shlex.quote(remote_dir)}",
                    timeout=120,
                    check=False,
                )
                remote_scratch_cleanup = cleanup.returncode == 0
            if final_result is not None and remote_scratch_cleanup is True:
                post_cleanup_storage = remote_storage_report(
                    args.target,
                    control_path,
                )
                post_cleanup_free = min(
                    int(post_cleanup_storage["staging_free_bytes"]),
                    int(post_cleanup_storage["docker_free_bytes"]),
                    int(post_cleanup_storage["image_store_free_bytes"]),
                )
                if post_cleanup_free < P5_POST_PEAK_RESERVE_BYTES:
                    raise StopExecution("post_cleanup_runtime_reserve_breached")
                final_result["post_cleanup_free_bytes"] = post_cleanup_free
                final_result["post_cleanup_reserve_bytes"] = (
                    P5_POST_PEAK_RESERVE_BYTES
                )
                final_result["post_cleanup_reserve_pass"] = True
            run(
                ["ssh", *ssh_options(control_path), "-O", "exit", args.target],
                timeout=30,
                check=False,
            )
            try:
                Path(control_path).unlink(missing_ok=True)
            except OSError:
                pass

        if final_result is None:
            raise StopExecution("unexpected_executor_fallthrough")
        if remote_scratch_cleanup is not True:
            raise StopExecution("remote_scratch_cleanup_failed_after_apply")
        final_result["remote_scratch_cleanup"] = True
        write_private(evidence / "result.json", final_result)
        return final_result

def main() -> int:
    parser = argparse.ArgumentParser(prog="n3w-ha-p5-live-apply")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-source-head", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()

    if not args.execute:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "gate_id": GATE_ID,
                    "status": "STOP",
                    "reason": "execute_flag_required",
                    "authorization_claimed": False,
                    "authorization_consumed": False,
                    "t1_mutation": False,
                },
                sort_keys=True,
            )
        )
        return 2

    try:
        result = execute(args)
    except Exception as error:
        reason = str(error)
        if (
            not reason
            or len(reason) > 200
            or "/" in reason
            or "\\" in reason
            or "@" in reason
        ):
            reason = type(error).__name__
        evidence = args.evidence_root.expanduser()
        claim_exists = (evidence / "authorization-claim.json").is_file()
        apply_path = evidence / "apply.json"
        apply_exists = apply_path.is_file()
        mutation: bool | str = False
        if apply_exists:
            mutation = "UNKNOWN"
            try:
                apply_doc = read_json(apply_path)
                if apply_doc.get("status") == "PASS" and apply_doc.get("t1_mutation") is True:
                    mutation = True
            except Exception:
                mutation = "UNKNOWN"
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "gate_id": GATE_ID,
                    "status": "STOP",
                    "reason": reason,
                    "authorization_claimed": claim_exists,
                    "authorization_consumed": claim_exists,
                    "t1_mutation": mutation,
                    "apply_invoked": apply_exists or claim_exists,
                    "second_apply_allowed": False,
                    "blind_explicit_rollback_allowed": False,
                },
                sort_keys=True,
            )
        )
        return 2

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
