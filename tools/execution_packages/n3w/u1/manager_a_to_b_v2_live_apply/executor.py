#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"

REPOSITORY = "chrenguo-stack/HomeAssistant"
RUN_ID = "41841275491"
RUN_NUMBER = 179
ARTIFACT_ID = 13329432192
ARTIFACT_NAME = "n3w-t1-core-updater-manager-v2-5b32e1ae8210"
ARTIFACT_DIGEST = "sha256:b2cd55cf11de3a97f5d0df13e790094778b76582e1c885318387a8368b6ecfc5"
ARTIFACT_HEAD = "29f3094a08f28f4f6660f2394fc90a6d66ab6c79"
UPDATER_PYZ_SHA256 = "17849b16c0f60b30b69bcd7d0a17826058748fff053a93a3d90cf349c5baded7"
MANAGER_TAR_SHA256 = "2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa"

TARGET_RELATIVE = "infra/n3w-t1/upgrades/manager-5b32e1ae8210.json"
BASELINE_RELATIVE = "infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json"
EXPECTED_PREDECESSOR = "local/greenhouse-manager:fresh-b863ddd95909"
TARGET_MANAGER = "local/greenhouse-manager:fresh-5b32e1ae8210"
TARGET_SCHEMA = "gh.n3w-t1-core-updater-target/2"
TX_SCHEMA = "gh.n3w-t1-core-updater-transaction/2"
STATUS_SCHEMA = "gh.n3w-t1-core-updater-status/2"
LEGACY_STATUS_SCHEMA = "gh.n3w-t1-core-updater-status/1"
LEGACY_TX_SCHEMA = "gh.n3w-t1-core-updater-transaction/1"
INSPECT_SCHEMA = "gh.n3w-t1-core-updater-inspect/2"
PLAN_SCHEMA = "gh.n3w-t1-core-updater-plan/2"

AUTHORIZATION = "N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_U1_V2_20261104_02"
CONFIRMATION = "EXECUTE U1 V2 MANAGER A TO B: YES"
APPLY_CONFIRMATION = "T1_CORE_UPDATER_APPLY"
REMOTE_DIR = "/var/tmp/n3w-u1-manager-a-to-b-v2-20261104-02"

EXPECTED_PACKAGE_FILES = {
    "greenhouse-manager-arm64.tar",
    "manager-target-v2.json",
    "upgrade-baseline-a.json",
    "package-binding.json",
    "t1-core-updater.pyz",
}


class StopExecution(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution(f"json_invalid:{path.name}") from error
    if not isinstance(value, dict):
        raise StopExecution(f"json_shape_invalid:{path.name}")
    return value


def run(
    argv: list[str],
    *,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
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
    result = run(["git", "-C", str(REPO_ROOT), *args], timeout=30)
    return result.stdout.strip()


def validate_local_source(expected_commit: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit) is None:
        raise StopExecution("expected_package_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise StopExecution("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("tracked_worktree_dirty")
    manifest = read_json(MANIFEST_PATH)
    if manifest.get("authorization_id") != AUTHORIZATION:
        raise StopExecution("manifest_authorization_mismatch")
    if manifest.get("package_authority", {}).get("artifact_id") != ARTIFACT_ID:
        raise StopExecution("manifest_artifact_mismatch")


def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise StopExecution("evidence_root_invalid")
        if stat.S_IMODE(root.stat().st_mode) != 0o700:
            os.chmod(root, 0o700)
    else:
        root.mkdir(parents=True, mode=0o700)
    return root


def write_private(path: Path, value: Any) -> None:
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


def parse_json_output(result: subprocess.CompletedProcess[str], operation: str) -> dict[str, Any]:
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise StopExecution(f"{operation}_json_invalid") from error
    if not isinstance(value, dict):
        raise StopExecution(f"{operation}_json_shape_invalid")
    return value


def verify_github_artifact(download_root: Path) -> tuple[Path, dict[str, Any]]:
    metadata_result = run(
        [
            "gh",
            "api",
            f"repos/{REPOSITORY}/actions/artifacts/{ARTIFACT_ID}",
        ],
        timeout=60,
    )
    try:
        metadata = json.loads(metadata_result.stdout)
    except json.JSONDecodeError as error:
        raise StopExecution("artifact_metadata_invalid") from error
    if (
        metadata.get("id") != ARTIFACT_ID
        or metadata.get("name") != ARTIFACT_NAME
        or metadata.get("digest") != ARTIFACT_DIGEST
        or metadata.get("expired") is not False
        or metadata.get("workflow_run", {}).get("id") != int(RUN_ID)
        or metadata.get("workflow_run", {}).get("head_sha") != ARTIFACT_HEAD
    ):
        raise StopExecution("artifact_metadata_mismatch")

    package = download_root / "package"
    package.mkdir()
    run(
        [
            "gh",
            "run",
            "download",
            RUN_ID,
            "-R",
            REPOSITORY,
            "-n",
            ARTIFACT_NAME,
            "-D",
            str(package),
        ],
        timeout=600,
    )
    observed = {item.name for item in package.iterdir()}
    if observed != EXPECTED_PACKAGE_FILES:
        raise StopExecution("package_file_set_mismatch")

    tar = package / "greenhouse-manager-arm64.tar"
    pyz = package / "t1-core-updater.pyz"
    if sha256_file(tar) != MANAGER_TAR_SHA256:
        raise StopExecution("manager_tar_sha256_mismatch")
    if sha256_file(pyz) != UPDATER_PYZ_SHA256:
        raise StopExecution("updater_pyz_sha256_mismatch")

    repo_target = read_json(REPO_ROOT / TARGET_RELATIVE)
    repo_baseline = read_json(REPO_ROOT / BASELINE_RELATIVE)
    package_target = read_json(package / "manager-target-v2.json")
    package_baseline = read_json(package / "upgrade-baseline-a.json")
    binding = read_json(package / "package-binding.json")

    if canonical(repo_target) != canonical(package_target):
        raise StopExecution("package_target_repo_mismatch")
    if canonical(repo_baseline) != canonical(package_baseline):
        raise StopExecution("package_baseline_repo_mismatch")

    if (
        package_target.get("schema") != TARGET_SCHEMA
        or package_target.get("component") != "manager"
        or package_target.get("expected_predecessor_image_ref") != EXPECTED_PREDECESSOR
        or package_target.get("target_image_ref") != TARGET_MANAGER
        or package_target.get("target_archive_sha256") != MANAGER_TAR_SHA256
        or package_target.get("rollback_compatible") is not True
    ):
        raise StopExecution("target_contract_mismatch")

    if (
        binding.get("schema") != "gh.n3w-t1-core-updater-manager-package/2"
        or binding.get("control_plane_head") != ARTIFACT_HEAD
        or binding.get("target_schema") != TARGET_SCHEMA
        or binding.get("transaction_schema") != TX_SCHEMA
        or binding.get("upstream_artifact_id") != 13319777217
        or binding.get("manager_image") != TARGET_MANAGER
        or binding.get("manager_tar_sha256") != MANAGER_TAR_SHA256
        or binding.get("updater_pyz_sha256") != UPDATER_PYZ_SHA256
        or binding.get("manager_rebuilt") is not False
        or binding.get("homeassistant_included") is not False
        or binding.get("broker_included") is not False
        or binding.get("t1_mutation") is not False
    ):
        raise StopExecution("package_binding_mismatch")

    return package, {
        "metadata": metadata,
        "target": package_target,
        "baseline": package_baseline,
        "binding": binding,
    }


def validate_target(target: str) -> None:
    if (
        not target
        or target.strip() != target
        or any(ch.isspace() for ch in target)
        or target.startswith("-")
        or any(mark in target.casefold() for mark in ("placeholder", "example", "<", ">"))
    ):
        raise StopExecution("t1_target_invalid")


def ssh_base(target: str, control_path: str) -> list[str]:
    validate_target(target)
    if not control_path.startswith("/"):
        raise StopExecution("control_path_invalid")
    return [
        "ssh",
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
        target,
    ]


def scp_base(control_path: str) -> list[str]:
    return [
        "scp",
        "-q",
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
    ]


def ssh_command(
    target: str,
    control_path: str,
    command: str,
    *,
    timeout: int = 180,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run(
        [*ssh_base(target, control_path), command],
        timeout=timeout,
        check=check,
    )


def remote_updater_command(
    target: str,
    control_path: str,
    args: list[str],
    *,
    timeout: int,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    pyz = f"{REMOTE_DIR}/t1-core-updater.pyz"
    command = " ".join(
        shlex.quote(item)
        for item in ["sudo", "-n", "python3", "-B", pyz, *args]
    )
    return ssh_command(
        target,
        control_path,
        command,
        timeout=timeout,
        check=check,
    )


def stage_package(
    package: Path,
    target: str,
    control_path: str,
) -> dict[str, str]:
    local_hashes = {
        name: sha256_file(package / name)
        for name in sorted(EXPECTED_PACKAGE_FILES)
    }
    quoted = shlex.quote(REMOTE_DIR)
    probe = ssh_command(
        target,
        control_path,
        (
            f"if sudo -n test -e {quoted}; then "
            f"sudo -n stat -c '%U:%G:%a:%F' {quoted}; "
            f"sudo -n find {quoted} -mindepth 1 -maxdepth 1 -printf '%f\\n' | sort; "
            "else echo __ABSENT__; fi"
        ),
        timeout=60,
    )
    lines = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
    if lines == ["__ABSENT__"]:
        ssh_command(
            target,
            control_path,
            f"sudo -n install -d -m 0700 -o root -g root {quoted}",
            timeout=60,
        )
        for name in sorted(EXPECTED_PACKAGE_FILES):
            run(
                [
                    *scp_base(control_path),
                    str(package / name),
                    f"{target}:{REMOTE_DIR}/{name}",
                ],
                timeout=600,
            )
    else:
        if not lines or lines[0] != "root:root:700:directory":
            raise StopExecution("remote_staging_metadata_invalid")
        if set(lines[1:]) != EXPECTED_PACKAGE_FILES:
            raise StopExecution("remote_staging_file_set_mismatch")

    remote = ssh_command(
        target,
        control_path,
        " && ".join(
            f"sudo -n sha256sum {shlex.quote(REMOTE_DIR + '/' + name)}"
            for name in sorted(EXPECTED_PACKAGE_FILES)
        ),
        timeout=180,
    )
    remote_hashes: dict[str, str] = {}
    for line in remote.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            raise StopExecution("remote_sha256_output_invalid")
        remote_hashes[Path(parts[1]).name] = parts[0]
    if remote_hashes != local_hashes:
        raise StopExecution("remote_package_sha256_mismatch")
    return local_hashes


def require_terminal_status(document: dict[str, Any]) -> None:
    if (
        document.get("status") != "PASS"
        or document.get("operation") != "status"
        or document.get("mutation") is not False
        or document.get("recovery_required") is not False
    ):
        raise StopExecution("fresh_status_invalid")

    schema = document.get("schema")
    tx = document.get("transaction")
    if not isinstance(tx, dict):
        raise StopExecution("fresh_terminal_transaction_missing")

    if schema == STATUS_SCHEMA:
        if (
            tx.get("schema") != TX_SCHEMA
            or tx.get("status") not in {"COMMITTED", "ROLLED_BACK"}
        ):
            raise StopExecution("fresh_v2_terminal_transaction_invalid")
        legacy = document.get("legacy_manager_transaction")
        if (
            isinstance(legacy, dict)
            and legacy.get("status") not in {"COMMITTED", "ROLLED_BACK"}
        ):
            raise StopExecution("fresh_legacy_transaction_nonterminal")
        return

    if schema == LEGACY_STATUS_SCHEMA:
        if (
            tx.get("schema") != LEGACY_TX_SCHEMA
            or tx.get("status") not in {"COMMITTED", "ROLLED_BACK"}
        ):
            raise StopExecution("fresh_legacy_terminal_transaction_invalid")
        return

    raise StopExecution("fresh_status_schema_invalid")


def require_inspect(document: dict[str, Any], baseline: dict[str, Any], manager: str) -> None:
    if (
        document.get("schema") != INSPECT_SCHEMA
        or document.get("status") != "PASS"
        or document.get("operation") != "inspect"
        or document.get("component") != "manager"
        or document.get("mutation") is not False
    ):
        raise StopExecution("fresh_inspect_invalid")
    snapshot = document.get("snapshot")
    if not isinstance(snapshot, dict):
        raise StopExecution("fresh_inspect_snapshot_invalid")
    bindings = snapshot.get("image_bindings")
    modes = snapshot.get("image_binding_modes")
    if not isinstance(bindings, dict) or not isinstance(modes, dict):
        raise StopExecution("fresh_binding_authority_invalid")
    expected = baseline.get("stack_images")
    if not isinstance(expected, dict):
        raise StopExecution("baseline_stack_images_invalid")
    if bindings.get("manager") != manager:
        raise StopExecution("manager_binding_mismatch")
    for peer in ("homeassistant", "broker"):
        if bindings.get(peer) != expected.get(peer):
            raise StopExecution(f"{peer}_binding_drift")
    if any(modes.get(name) != "dynamic" for name in ("manager", "homeassistant", "broker")):
        raise StopExecution("dynamic_binding_required")
    mqtt = snapshot.get("mqtt_authenticated")
    if not isinstance(mqtt, dict) or mqtt.get("manager") is not True or mqtt.get("homeassistant") is not True:
        raise StopExecution("mqtt_authentication_missing")
    listeners = snapshot.get("listeners")
    if not isinstance(listeners, dict):
        raise StopExecution("listener_contract_missing")
    expected_listeners = {
        "tcp_8883": 1,
        "tcp_47110": 1,
        "udp_47111": 1,
        "tcp_47112": 0,
    }
    if {key: listeners.get(key) for key in expected_listeners} != expected_listeners:
        raise StopExecution("listener_contract_drift")


def require_plan(document: dict[str, Any]) -> None:
    if (
        document.get("schema") != PLAN_SCHEMA
        or document.get("status") != "PASS"
        or document.get("operation") != "plan"
        or document.get("component") != "manager"
        or document.get("mutation") is not False
        or document.get("rollback_available") is not True
        or document.get("target_archive_verified") is not True
    ):
        raise StopExecution("fresh_plan_invalid")
    current = document.get("current")
    target = document.get("target")
    if not isinstance(current, dict) or current.get("image") != EXPECTED_PREDECESSOR:
        raise StopExecution("fresh_plan_predecessor_mismatch")
    if not isinstance(target, dict) or target.get("target_image_ref") != TARGET_MANAGER:
        raise StopExecution("fresh_plan_target_mismatch")
    if document.get("target_image_prestate") not in {"ABSENT", "PRESENT_AND_EXACT"}:
        raise StopExecution("fresh_plan_target_prestate_invalid")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.authorization_id != AUTHORIZATION:
        raise StopExecution("authorization_id_mismatch")
    if args.confirm != CONFIRMATION:
        raise StopExecution("execution_confirmation_mismatch")
    validate_local_source(args.expected_package_commit)
    root = prepare_evidence_root(args.evidence_root)

    closure: dict[str, Any] = {
        "schema": "gh.n3w-t1-core-updater-u1-v2-live-execution-result/1",
        "status": "STOP",
        "execution_id": args.execution_id,
        "authorization_id": AUTHORIZATION,
        "authorization_granted": True,
        "authorization_claimed": False,
        "authorization_consumed_by_executor": False,
        "replay_permitted": False,
        "package_run_id": int(RUN_ID),
        "package_artifact_id": ARTIFACT_ID,
        "package_artifact_digest": ARTIFACT_DIGEST,
        "t1_access": False,
        "t1_file_write": False,
        "apply_invoked": False,
        "second_apply_invoked": False,
        "automatic_rollback": False,
        "board_access": False,
        "first_failed_operation": None,
    }

    work = Path(tempfile.mkdtemp(prefix="n3w-u1-v2-package."))
    try:
        package, package_info = verify_github_artifact(work)
        write_private(root / "package_authority.json", package_info)

        closure["t1_access"] = True
        hashes = stage_package(package, args.t1_ssh_target, args.control_path)
        closure["t1_file_write"] = True
        write_private(root / "remote_package_hashes.json", hashes)

        status_result = remote_updater_command(
            args.t1_ssh_target,
            args.control_path,
            ["status"],
            timeout=120,
            check=True,
        )
        status_doc = parse_json_output(status_result, "status")
        write_private(root / "pre_status.json", status_doc)
        require_terminal_status(status_doc)

        inspect_result = remote_updater_command(
            args.t1_ssh_target,
            args.control_path,
            ["inspect", "--component", "manager"],
            timeout=180,
            check=True,
        )
        inspect_doc = parse_json_output(inspect_result, "inspect")
        write_private(root / "pre_inspect.json", inspect_doc)
        require_inspect(inspect_doc, package_info["baseline"], EXPECTED_PREDECESSOR)

        plan_args = [
            "plan",
            "--target-manifest",
            f"{REMOTE_DIR}/manager-target-v2.json",
            "--baseline-manifest",
            f"{REMOTE_DIR}/upgrade-baseline-a.json",
            "--manager-tar",
            f"{REMOTE_DIR}/greenhouse-manager-arm64.tar",
        ]
        plan_result = remote_updater_command(
            args.t1_ssh_target,
            args.control_path,
            plan_args,
            timeout=300,
            check=True,
        )
        plan_doc = parse_json_output(plan_result, "plan")
        write_private(root / "pre_plan.json", plan_doc)
        require_plan(plan_doc)

        closure["authorization_claimed"] = True
        closure["authorization_consumed_by_executor"] = True
        closure["apply_invoked"] = True
        write_private(
            root / "authorization_claim.json",
            {
                "authorization_id": AUTHORIZATION,
                "claimed": True,
                "consumed_by_executor": True,
                "replay_permitted": False,
                "reason": "single live apply invocation begins",
            },
        )

        apply_args = [
            "apply",
            "--target-manifest",
            f"{REMOTE_DIR}/manager-target-v2.json",
            "--baseline-manifest",
            f"{REMOTE_DIR}/upgrade-baseline-a.json",
            "--manager-tar",
            f"{REMOTE_DIR}/greenhouse-manager-arm64.tar",
            "--authorization-id",
            AUTHORIZATION,
            "--confirmation",
            APPLY_CONFIRMATION,
        ]
        apply_result = remote_updater_command(
            args.t1_ssh_target,
            args.control_path,
            apply_args,
            timeout=900,
            check=False,
        )
        apply_doc: dict[str, Any] | None = None
        try:
            apply_doc = parse_json_output(apply_result, "apply")
            write_private(root / "apply.json", apply_doc)
        except StopExecution:
            write_private(
                root / "apply_transport.json",
                {
                    "returncode": apply_result.returncode,
                    "stdout_sha256": hashlib.sha256(apply_result.stdout.encode()).hexdigest(),
                    "stderr_sha256": hashlib.sha256(apply_result.stderr.encode()).hexdigest(),
                },
            )

        post_status_result = remote_updater_command(
            args.t1_ssh_target,
            args.control_path,
            ["status"],
            timeout=120,
            check=False,
        )
        post_inspect_result = remote_updater_command(
            args.t1_ssh_target,
            args.control_path,
            ["inspect", "--component", "manager"],
            timeout=180,
            check=False,
        )
        post_status = parse_json_output(post_status_result, "post_status")
        post_inspect = parse_json_output(post_inspect_result, "post_inspect")
        write_private(root / "post_status.json", post_status)
        write_private(root / "post_inspect.json", post_inspect)

        if (
            apply_result.returncode != 0
            or not isinstance(apply_doc, dict)
            or apply_doc.get("status") != "PASS"
            or apply_doc.get("operation") != "apply"
            or apply_doc.get("transaction_status") != "COMMITTED"
            or apply_doc.get("authorization_consumed") is not True
            or apply_doc.get("t1_mutation") is not True
        ):
            raise StopExecution("apply_not_committed")

        if (
            post_status.get("schema") != STATUS_SCHEMA
            or post_status.get("status") != "PASS"
            or post_status.get("recovery_required") is not False
        ):
            raise StopExecution("post_status_invalid")
        tx = post_status.get("transaction")
        if (
            not isinstance(tx, dict)
            or tx.get("schema") != TX_SCHEMA
            or tx.get("status") != "COMMITTED"
            or tx.get("phase") != "COMMITTED"
            or tx.get("target", {}).get("target_image_ref") != TARGET_MANAGER
        ):
            raise StopExecution("post_transaction_invalid")

        require_inspect(post_inspect, package_info["baseline"], TARGET_MANAGER)

        closure["status"] = "PASS"
        closure["transaction_status"] = "COMMITTED"
        closure["manager_after"] = TARGET_MANAGER
        closure["recovery_required"] = False
        return closure
    except StopExecution as error:
        closure["first_failed_operation"] = str(error)
        return closure
    finally:
        write_private(root / "closure.json", closure)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true")
    p.add_argument("--expected-package-commit")
    p.add_argument("--authorization-id")
    p.add_argument("--execution-id")
    p.add_argument("--evidence-root", type=Path)
    p.add_argument("--t1-ssh-target")
    p.add_argument("--control-path")
    p.add_argument("--confirm", default="")
    return p


def main() -> int:
    args = parser().parse_args()
    required = (
        args.expected_package_commit,
        args.authorization_id,
        args.execution_id,
        args.evidence_root,
        args.t1_ssh_target,
        args.control_path,
    )
    if not args.execute or any(value is None for value in required):
        print(json.dumps({"status": "STOP", "reason": "execution_arguments_missing"}))
        return 2
    try:
        result = execute(args)
    except StopExecution as error:
        result = {
            "schema": "gh.n3w-t1-core-updater-u1-v2-live-execution-result/1",
            "status": "STOP",
            "first_failed_operation": str(error),
            "apply_invoked": False,
            "replay_permitted": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
