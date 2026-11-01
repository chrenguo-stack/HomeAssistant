#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

SCHEMA = "gh.n3w-t1-clean-reference-r2b/1"
PACKAGE_SCHEMA = "gh.n3w-t1-clean-reference-r2b-package/1"
TRANSACTION_SCHEMA = "gh.n3w-t1-clean-reference-r2b-transaction/1"

PRODUCT_SOURCE_HEAD = "24382caae4a1f5d459297f86e8d18f10a848ca64"
R2A_CONTROL_HEAD = "abeb6c31147bcf249361dcec7e9536eaed6106a6"
R2A_TRANSACTION_SCHEMA = "gh.n3w-t1-clean-reference-r2a-transaction/1"

CONFIRMATION = "REBOOT N3W T1 CLEAN REFERENCE R2B: YES"
AUTHORIZATION_PREFIX = "N3W_T1_CORE_STACK_CLEAN_REFERENCE_R2B_"

R2A_TRANSACTION = Path(
    "/var/lib/n3w-t1-clean-reference-r2a/transaction.json"
)
STATE_ROOT = Path("/var/lib/n3w-t1-clean-reference-r2b")
TRANSACTION = STATE_ROOT / "transaction.json"
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")

COMPOSE = Path("/etc/n3wfc4/docker-compose.yml")
COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")

BROKER_UNIT = "n3wfc4-broker-activation.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
CERT_SERVICE = "n3wfc4-broker-certificate-lifecycle.service"
CERT_TIMER = "n3wfc4-broker-certificate-lifecycle.timer"
PROVISION_UNIT = "n3wfc4-provision-resume.service"
GUARD_UNIT = "n3wfc4-broker-ingress-guard.service"
REGISTRATION_GUARD_UNIT = "n3wfc4-registration-ingress-guard.service"

EXPECTED_SERVICES = frozenset({"broker", "manager", "homeassistant"})
EXPECTED_NETWORKS = frozenset(
    {"bridge", "host", "none", "n3wfc4-private", "n3wfc4-services"}
)

CERTIFICATE_FILES = (
    Path("/etc/n3wfc4/tls/ca.pem"),
    Path("/etc/n3wfc4/tls/server.pem"),
    Path("/etc/n3wfc4/tls/server.key"),
    Path("/opt/greenhouse-secrets/broker-ca/ca.key"),
    Path("/var/lib/greenhouse-manager/identity/system-ca.pem"),
)


class R2BError(RuntimeError):
    pass


def _emit(document: dict[str, object], *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    stream.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")


def _run(
    argv: Sequence[str],
    *,
    timeout: float = 120.0,
    allowed: frozenset[int] = frozenset({0}),
) -> str:
    completed = subprocess.run(
        tuple(argv),
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode not in allowed:
        reason = completed.stderr.strip() or completed.stdout.strip()
        raise R2BError(
            f"command_failed:{Path(argv[0]).name}:{completed.returncode}:{reason[:300]}"
        )
    return completed.stdout


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, *, mode: int | None = None) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise R2BError(f"record_invalid:{path}")
    metadata = path.stat()
    if mode is not None and (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
    ):
        raise R2BError(f"record_metadata_invalid:{path.name}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise R2BError(f"record_json_invalid:{path.name}") from error
    if not isinstance(document, dict):
        raise R2BError(f"record_document_invalid:{path.name}")
    return document


def _atomic_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise R2BError("transaction_parent_symlink")
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    replaced = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            stream.write(
                json.dumps(document, sort_keys=True, indent=2) + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.chown(temporary, 0, 0)
        os.replace(temporary, path)
        replaced = True
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not replaced:
            temporary.unlink(missing_ok=True)


def _boot_id() -> str:
    if BOOT_ID.is_symlink() or not BOOT_ID.is_file():
        raise R2BError("boot_id_invalid")
    value = BOOT_ID.read_text(encoding="ascii").strip().lower()
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        value,
    ) is None:
        raise R2BError("boot_id_invalid")
    return value


def _systemctl(mode: str, unit: str) -> str:
    completed = subprocess.run(
        ("systemctl", mode, unit),
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30,
    )
    return completed.stdout.strip() or "unknown"


def _package(root: Path) -> dict[str, object]:
    manifest_path = root / "package-manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("schema") != PACKAGE_SCHEMA:
        raise R2BError("package_schema_invalid")
    if manifest.get("product_source_head") != PRODUCT_SOURCE_HEAD:
        raise R2BError("package_product_source_invalid")
    if manifest.get("r2a_control_head") != R2A_CONTROL_HEAD:
        raise R2BError("package_r2a_control_invalid")
    control_head = manifest.get("control_plane_head")
    if not isinstance(control_head, str) or re.fullmatch(r"[0-9a-f]{40}", control_head) is None:
        raise R2BError("package_control_head_invalid")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 1:
        raise R2BError("package_files_invalid")
    record = files[0]
    if not isinstance(record, dict):
        raise R2BError("package_file_record_invalid")
    if record.get("path") != "tools/n3w_t1_clean_reference_r2b.py":
        raise R2BError("package_file_path_invalid")
    path = root / str(record["path"])
    if path.is_symlink() or not path.is_file():
        raise R2BError("package_executor_missing")
    if (
        path.stat().st_size != record.get("size")
        or _sha256(path) != record.get("sha256")
    ):
        raise R2BError("package_executor_binding_invalid")
    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item != manifest_path
    }
    if actual != {"tools/n3w_t1_clean_reference_r2b.py"}:
        raise R2BError("package_file_set_invalid")
    executing = Path(os.path.abspath(__file__))
    if (
        executing.is_symlink()
        or not executing.is_file()
        or executing != path
        or _sha256(executing) != record.get("sha256")
        or executing.stat().st_size != record.get("size")
    ):
        raise R2BError("executor_entrypoint_binding_invalid")
    return manifest


def _r2a_transaction() -> dict[str, object]:
    document = _read_json(R2A_TRANSACTION, mode=0o600)
    expected = {
        "schema": R2A_TRANSACTION_SCHEMA,
        "stage": "RUNTIME_STARTED",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "authorization_replay_allowed": False,
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "control_plane_head": R2A_CONTROL_HEAD,
        "runtime_started": True,
        "production_service_start": True,
        "persistence_enabled": True,
        "certificate_timer_enabled": True,
        "pre_reboot_ready": True,
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise R2BError(f"r2a_transaction_binding_invalid:{key}")
    if frozenset(document.get("runtime_services", [])) != EXPECTED_SERVICES:
        raise R2BError("r2a_runtime_service_set_invalid")
    return document


def _running_services() -> frozenset[str]:
    output = _run(
        (
            "docker",
            "compose",
            "--project-name",
            "n3wfc4",
            "--env-file",
            str(COMPOSE_ENV),
            "-f",
            str(COMPOSE),
            "--profile",
            "application",
            "ps",
            "--status",
            "running",
            "--services",
        ),
        timeout=60,
    )
    services = frozenset(line.strip() for line in output.splitlines() if line.strip())
    if services - EXPECTED_SERVICES:
        raise R2BError("runtime_service_set_unexpected")
    return services


def _container_snapshot() -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for service in sorted(EXPECTED_SERVICES):
        output = _run(
            (
                "docker",
                "ps",
                "--filter",
                "label=com.docker.compose.project=n3wfc4",
                "--filter",
                f"label=com.docker.compose.service={service}",
                "--format",
                "{{.ID}}",
            ),
            timeout=30,
        )
        ids = [line.strip() for line in output.splitlines() if line.strip()]
        if len(ids) != 1:
            raise R2BError(f"runtime_service_not_unique:{service}")
        try:
            documents = json.loads(_run(("docker", "inspect", ids[0]), timeout=30))
        except json.JSONDecodeError as error:
            raise R2BError(f"runtime_inspect_invalid:{service}") from error
        if not isinstance(documents, list) or len(documents) != 1:
            raise R2BError(f"runtime_inspect_invalid:{service}")
        document = documents[0]
        state = document.get("State")
        if (
            not isinstance(state, dict)
            or state.get("Running") is not True
            or not isinstance(document.get("Id"), str)
            or not isinstance(state.get("StartedAt"), str)
            or not state.get("StartedAt")
            or type(document.get("RestartCount")) is not int
        ):
            raise R2BError(f"runtime_service_state_invalid:{service}")
        snapshot[service] = {
            "id": document["Id"],
            "started_at": state["StartedAt"],
            "restart_count": document["RestartCount"],
        }
    return snapshot


def _certificate_snapshot() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in CERTIFICATE_FILES:
        if path.is_symlink() or not path.is_file():
            raise R2BError(f"certificate_file_invalid:{path.name}")
        result[str(path)] = _sha256(path)
    return result


def _broker_readiness() -> None:
    _run(
        (
            "/usr/local/sbin/n3w-t1-broker-authenticated-readiness",
            "--metadata-file",
            "/opt/greenhouse-secrets/mqtt/homeassistant/mqtt-bootstrap.json",
            "--password-file",
            "/opt/greenhouse-secrets/mqtt/homeassistant/password",
            "--timeout-seconds",
            "120",
        ),
        timeout=150,
    )


def _ha_readiness(timeout_seconds: float = 60.0) -> int:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 8123), timeout=5) as stream:
                stream.settimeout(5)
                stream.sendall(
                    b"GET /api/ HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"Connection: close\r\n\r\n"
                )
                first = stream.recv(256).split(b"\r\n", 1)[0]
            parts = first.split()
            if (
                len(parts) >= 2
                and parts[0].startswith(b"HTTP/")
                and parts[1].isdigit()
                and int(parts[1]) in {200, 401}
            ):
                return int(parts[1])
        except OSError:
            pass
        time.sleep(2)
    raise R2BError("homeassistant_http_readiness_failed")


def _pre_reboot_state() -> dict[str, object]:
    r2a = _r2a_transaction()
    if TRANSACTION.exists() or TRANSACTION.is_symlink() or STATE_ROOT.exists() or STATE_ROOT.is_symlink():
        raise R2BError("r2b_transaction_state_present")
    if _running_services() != EXPECTED_SERVICES:
        raise R2BError("pre_reboot_runtime_service_set_invalid")
    for unit in (
        PROVISION_UNIT,
        GUARD_UNIT,
        REGISTRATION_GUARD_UNIT,
        BROKER_UNIT,
        SERVICES_UNIT,
    ):
        if _systemctl("is-active", unit) != "active":
            raise R2BError(f"pre_reboot_unit_not_active:{unit}")
    for unit in (
        PROVISION_UNIT,
        GUARD_UNIT,
        REGISTRATION_GUARD_UNIT,
        BROKER_UNIT,
        SERVICES_UNIT,
        CERT_TIMER,
    ):
        if _systemctl("is-enabled", unit) != "enabled":
            raise R2BError(f"pre_reboot_unit_not_enabled:{unit}")
    if _systemctl("is-active", CERT_TIMER) == "active":
        raise R2BError("pre_reboot_certificate_timer_active")
    if _systemctl("is-active", CERT_SERVICE) == "active":
        raise R2BError("pre_reboot_certificate_service_active")
    networks = frozenset(
        line.strip()
        for line in _run(("docker", "network", "ls", "--format", "{{.Name}}")).splitlines()
        if line.strip()
    )
    if networks != EXPECTED_NETWORKS:
        raise R2BError("pre_reboot_network_set_invalid")
    _broker_readiness()
    ha_status = _ha_readiness()
    return {
        "r2a_transaction": r2a,
        "r2a_transaction_sha256": _sha256(R2A_TRANSACTION),
        "boot_id": _boot_id(),
        "containers": _container_snapshot(),
        "certificates": _certificate_snapshot(),
        "homeassistant_http_status": ha_status,
    }


def claim(root: Path, confirmation: str, authorization_id: str) -> dict[str, object]:
    if confirmation != CONFIRMATION:
        raise R2BError("confirmation_invalid")
    if (
        not authorization_id.startswith(AUTHORIZATION_PREFIX)
        or len(authorization_id) > 200
        or not authorization_id.replace("_", "").replace("-", "").isalnum()
    ):
        raise R2BError("authorization_id_invalid")
    manifest = _package(root)
    pre = _pre_reboot_state()
    STATE_ROOT.mkdir(mode=0o700)
    os.chown(STATE_ROOT, 0, 0)
    os.chmod(STATE_ROOT, 0o700)
    transaction = {
        "schema": TRANSACTION_SCHEMA,
        "stage": "REBOOT_PENDING",
        "authorization_id": authorization_id,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "authorization_replay_allowed": False,
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "r2a_control_head": R2A_CONTROL_HEAD,
        "control_plane_head": manifest["control_plane_head"],
        "executor_sha256": manifest["files"][0]["sha256"],
        "r2a_transaction_sha256": pre["r2a_transaction_sha256"],
        "pre_boot_id": pre["boot_id"],
        "pre_containers": pre["containers"],
        "pre_certificate_sha256": pre["certificates"],
        "pre_homeassistant_http_status": pre["homeassistant_http_status"],
        "reboot_actuation_required": True,
        "reboot_acceptance_passed": False,
        "board_access": False,
    }
    _atomic_json(TRANSACTION, transaction)
    persisted = _read_json(TRANSACTION, mode=0o600)
    if persisted != transaction:
        raise R2BError("reboot_claim_persistence_mismatch")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": "REBOOT_PENDING",
        "authorization_id": authorization_id,
        "authorization_consumed": True,
        "authorization_replay_allowed": False,
        "pre_boot_id": pre["boot_id"],
        "r2a_transaction_unchanged": True,
        "runtime_services": sorted(EXPECTED_SERVICES),
        "broker_authenticated_readiness": True,
        "homeassistant_http_ready": True,
        "reboot_actuation_required": True,
        "reboot_executed": False,
        "board_access": False,
    }


def _wait_post_reboot(timeout_seconds: float = 300.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_reason = "not_started"
    while time.monotonic() < deadline:
        try:
            system_state = _run(
                ("systemctl", "is-system-running"),
                timeout=10,
                allowed=frozenset({0, 1}),
            ).strip()
            if system_state not in {"running", "degraded"}:
                last_reason = f"system_state:{system_state or 'empty'}"
                time.sleep(2)
                continue
            failed = _run(
                ("systemctl", "--failed", "--no-legend", "--plain"),
                timeout=20,
            ).strip()
            if failed:
                raise R2BError("post_reboot_failed_units_present")
            ready = True
            for unit in (
                PROVISION_UNIT,
                GUARD_UNIT,
                REGISTRATION_GUARD_UNIT,
                BROKER_UNIT,
                SERVICES_UNIT,
            ):
                if _systemctl("is-active", unit) != "active":
                    ready = False
                    last_reason = f"unit_not_active:{unit}"
                    break
            if not ready:
                time.sleep(2)
                continue
            if _systemctl("is-active", CERT_TIMER) != "active":
                last_reason = "certificate_timer_not_active"
                time.sleep(2)
                continue
            if _running_services() != EXPECTED_SERVICES:
                last_reason = "runtime_service_set_incomplete"
                time.sleep(2)
                continue
            _broker_readiness()
            _ha_readiness(timeout_seconds=10)
            return
        except R2BError as error:
            if str(error) == "post_reboot_failed_units_present":
                raise
            last_reason = str(error)
            time.sleep(2)
    raise R2BError("post_reboot_readiness_timeout:" + last_reason)


def verify(root: Path) -> dict[str, object]:
    manifest = _package(root)
    transaction = _read_json(TRANSACTION, mode=0o600)
    if (
        transaction.get("schema") != TRANSACTION_SCHEMA
        or transaction.get("stage") != "REBOOT_PENDING"
        or transaction.get("authorization_claimed") is not True
        or transaction.get("authorization_consumed") is not True
        or transaction.get("authorization_replay_allowed") is not False
        or transaction.get("reboot_acceptance_passed") is not False
        or transaction.get("product_source_head") != PRODUCT_SOURCE_HEAD
        or transaction.get("r2a_control_head") != R2A_CONTROL_HEAD
        or transaction.get("control_plane_head") != manifest.get("control_plane_head")
        or transaction.get("executor_sha256") != manifest["files"][0]["sha256"]
        or transaction.get("board_access") is not False
    ):
        raise R2BError("reboot_claim_invalid")
    current_boot = _boot_id()
    pre_boot = transaction.get("pre_boot_id")
    if not isinstance(pre_boot, str) or current_boot == pre_boot:
        raise R2BError("reboot_not_observed")
    if _sha256(R2A_TRANSACTION) != transaction.get("r2a_transaction_sha256"):
        raise R2BError("r2a_transaction_changed_across_reboot")
    _r2a_transaction()
    _wait_post_reboot()
    for unit in (
        PROVISION_UNIT,
        GUARD_UNIT,
        REGISTRATION_GUARD_UNIT,
        BROKER_UNIT,
        SERVICES_UNIT,
        CERT_TIMER,
    ):
        if _systemctl("is-enabled", unit) != "enabled":
            raise R2BError(f"post_reboot_unit_not_enabled:{unit}")
    if _systemctl("is-active", CERT_SERVICE) == "active":
        raise R2BError("certificate_service_not_quiescent")
    services = _running_services()
    if services != EXPECTED_SERVICES:
        raise R2BError("post_reboot_runtime_service_set_invalid")
    networks = frozenset(
        line.strip()
        for line in _run(("docker", "network", "ls", "--format", "{{.Name}}")).splitlines()
        if line.strip()
    )
    if networks != EXPECTED_NETWORKS:
        raise R2BError("post_reboot_network_set_invalid")
    post_containers = _container_snapshot()
    pre_containers = transaction.get("pre_containers")
    if not isinstance(pre_containers, dict):
        raise R2BError("pre_container_snapshot_invalid")
    for service in EXPECTED_SERVICES:
        before = pre_containers.get(service)
        after = post_containers.get(service)
        if (
            not isinstance(before, dict)
            or not isinstance(after, dict)
            or before.get("started_at") == after.get("started_at")
        ):
            raise R2BError(f"container_start_time_not_refreshed:{service}")
    post_certificates = _certificate_snapshot()
    if post_certificates != transaction.get("pre_certificate_sha256"):
        raise R2BError("certificate_identity_changed_across_reboot")
    _broker_readiness()
    ha_status = _ha_readiness()
    time.sleep(30)
    stable = _container_snapshot()
    for service in EXPECTED_SERVICES:
        if stable[service]["id"] != post_containers[service]["id"]:
            raise R2BError(f"post_reboot_container_identity_changed:{service}")
        if stable[service]["started_at"] != post_containers[service]["started_at"]:
            raise R2BError(f"post_reboot_container_restart_detected:{service}")
    final_boot = _boot_id()
    if final_boot != current_boot:
        raise R2BError("second_reboot_observed")
    transaction.update(
        {
            "stage": "REBOOT_ACCEPTED",
            "reboot_acceptance_passed": True,
            "post_boot_id": current_boot,
            "post_containers": post_containers,
            "post_certificate_sha256": post_certificates,
            "homeassistant_http_status": ha_status,
            "post_reboot_stability_seconds": 30,
        }
    )
    _atomic_json(TRANSACTION, transaction)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": "REBOOT_ACCEPTED",
        "authorization_id": transaction["authorization_id"],
        "authorization_consumed": True,
        "authorization_replay_allowed": False,
        "pre_boot_id": pre_boot,
        "post_boot_id": current_boot,
        "reboot_observed": True,
        "r2a_transaction_unchanged": True,
        "runtime_services": sorted(services),
        "production_units_enabled": True,
        "production_units_active": True,
        "certificate_timer_enabled": True,
        "certificate_timer_active": True,
        "certificate_service_quiescent": True,
        "certificate_identity_unchanged": True,
        "broker_authenticated_readiness": True,
        "homeassistant_http_ready": True,
        "homeassistant_http_status": ha_status,
        "container_stability_seconds": 30,
        "same_boot_during_postcheck": True,
        "reboot_acceptance_passed": True,
        "board_access": False,
    }


def status() -> dict[str, object]:
    present = TRANSACTION.is_file() and not TRANSACTION.is_symlink()
    transaction = _read_json(TRANSACTION, mode=0o600) if present else None
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "transaction_present": present,
        "transaction_stage": transaction.get("stage") if transaction else "UNCLAIMED",
        "authorization_consumed": transaction.get("authorization_consumed") if transaction else False,
        "reboot_acceptance_passed": transaction.get("reboot_acceptance_passed") if transaction else False,
        "current_boot_id": _boot_id(),
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-clean-reference-r2b")
    sub = parser.add_subparsers(dest="command", required=True)
    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--package-root", required=True)
    claim_parser.add_argument("--confirm", required=True)
    claim_parser.add_argument("--authorization-id", required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--package-root", required=True)
    sub.add_parser("status")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "claim":
            report = claim(
                Path(os.path.abspath(args.package_root)),
                args.confirm,
                args.authorization_id,
            )
        elif args.command == "verify":
            report = verify(Path(os.path.abspath(args.package_root)))
        else:
            report = status()
    except (R2BError, OSError, subprocess.SubprocessError, ValueError) as error:
        _emit(
            {
                "schema": SCHEMA,
                "status": "STOP",
                "reason": str(error)[:300],
                "board_access": False,
            },
            error=True,
        )
        return 2
    _emit(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
