#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import secrets
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from n3w_t1_f5_v2_release_builder import verify_release_directory
from n3w_t1_failure_forensics import (
    build_manifest,
    collect_snapshot,
    freeze_failure,
    reflash_disposition,
)
from n3w_t1_fresh_armbian_qualification import collect as collect_qualification
from n3w_t1_post_reboot_acceptance import (
    MAX_SAMPLE_GAP_SECONDS,
    SAMPLE_INTERVAL_SECONDS,
    require_continuity,
    run_acceptance,
)
from n3w_t1_production_v2 import EvidenceInsufficientError, R3Orchestrator
from n3w_t1_production_v2_contract import (
    canonical_json_bytes,
    canonical_sha256,
    validate_release,
)
from n3w_t1_ssh_transport import SSHTransport

SCHEMA = "gh.n3w-t1-production-v2-live-executor/1"
APPROVAL_PREFIX = "APPROVE N3W T1 F5 V2 PRODUCTION"
REBOOT_ARM_PREFIX = "ARM N3W T1 F5 V2 CONTROLLED REBOOT"
PROGRESS_SCHEMA = "gh.n3w-t1-f5-v2-production-progress/1"
MARKER_PATH = "/var/lib/n3w-production/run.json"
F4_TRANSACTION_PATH = "/var/lib/n3w-t1-provisioning/F4_ACTIVATION_TRANSACTION.json"
REBOOT_CLAIM_PATH = "/var/lib/n3w-t1-provisioning/F4_REBOOT_AUTHORIZATION.json"
PROVISION_CLI = "/usr/local/sbin/n3w-t1-provision"
F4_CLI = "/usr/local/sbin/n3w-t1-f4-activation"
REBOOT_AUTHORITY_CLI = "/usr/local/sbin/n3w-t1-f4-reboot-authority"
REBOOT_VERIFY_CLI = "/usr/local/sbin/n3w-t1-f4-reboot-verify"
COMPOSE_FILE = "/etc/n3wfc4/docker-compose.yml"
BROKER_TLS_PORT = 8883
HOMEASSISTANT_PORT = 8123
TLS_SERVER_NAME = "armbian"
SSH_WAIT_SECONDS = 180
REBOOT_DISCONNECT_SECONDS = 45
REBOOT_TCP_DOWN_POLL_SECONDS = 0.5
REBOOT_TCP_PROBE_TIMEOUT_SECONDS = 1.0
REBOOT_TCP_DOWN_CONFIRMATIONS = 2
READINESS_TIMEOUT_SECONDS = 300
READINESS_POLL_SECONDS = 2
READINESS_SCHEMA = "gh.n3w-t1-f4-reboot-readiness/1"
TARGET_VERIFY_REPORT_SCHEMA = "gh.n3w-t1-f4-reboot-acceptance/1"
REPOSITORY_DEFINED_ERROR_CODES = frozenset(
    {
        "boot_id_invalid",
        "broker_authenticated_connection_evidence_missing",
        "broker_authenticated_connection_identity_mismatch",
        "broker_authenticated_connection_state_invalid",
        "broker_current_session_authentication_evidence_missing",
        "broker_log_coverage_insufficient",
        "certificate_identity_changed_across_reboot",
        "certificate_runtime_guard_dropin_missing",
        "certificate_runtime_guard_not_pass",
        "certificate_service_not_quiescent",
        "certificate_service_post_reboot_invalid",
        "certificate_unit_state_invalid",
        "control_binding_claim_invalid",
        "control_manifest_binding_invalid",
        "control_manifest_file_path_invalid",
        "control_manifest_file_record_invalid",
        "control_manifest_file_set_invalid",
        "control_manifest_files_invalid",
        "critical_systemd_unit_failed",
        "critical_systemd_unit_not_active",
        "evidence_insufficient",
        "f4_host_import_invalid",
        "f4_host_invalid",
        "f4_transaction_changed_across_reboot",
        "f4_transaction_post_reboot_invalid",
        "homeassistant_mqtt_socket_missing",
        "manager_mqtt_socket_count_invalid",
        "manager_runtime_identity_invalid",
        "mqtt_owned_socket_not_unique",
        "post_reboot_business_state_invalid",
        "post_reboot_unit_contract_invalid",
        "readiness_certificate_service_invalid",
        "readiness_certificate_timer_failed",
        "readiness_certificate_timer_not_enabled",
        "readiness_certificate_timer_state_invalid",
        "readiness_required_unit_failed",
        "readiness_required_unit_missing",
        "readiness_required_unit_state_invalid",
        "readiness_runtime_service_name_invalid",
        "readiness_systemd_not_operational",
        "readiness_systemd_state_invalid",
        "readiness_unit_evidence_invalid",
        "readiness_unit_load_state_invalid",
        "readiness_unit_state_invalid",
        "reboot_claim_invalid",
        "reboot_not_observed",
        "runtime_container_name_missing",
        "runtime_homeassistant_not_ready",
        "runtime_identity_invalid",
        "runtime_service_set_invalid",
        "runtime_snapshot_command_evidence_unavailable",
        "runtime_socket_auth_evidence_unstable",
        "runtime_socket_evidence_invalid",
        "snapshot_container_not_running",
        "snapshot_transaction_binding_changed",
        "systemd_error_coverage_insufficient",
        "systemd_error_cursor_missing",
        "verification_error",
        "verify_failed",
    }
)
REPOSITORY_DEFINED_ERROR_CODE_PATTERNS = (
    re.compile(
        r"record_(?:invalid|metadata_invalid|json_invalid|document_invalid):"
        r"[A-Za-z0-9_.-]+"
    ),
    re.compile(
        r"(?:unit_not_successful|oneshot_not_successful):[A-Za-z0-9_.@-]+"
    ),
    re.compile(
        r"runtime_service_set_unexpected:"
        r"[A-Za-z0-9_.-]+(?:,[A-Za-z0-9_.-]+)*"
    ),
)
SANITIZED_COMMAND_FAILURE_RE = re.compile(
    r"command_failed:[A-Za-z0-9_.-]+:[0-9]+"
)


def _repository_defined_error_code(value: str) -> bool:
    return (
        value in REPOSITORY_DEFINED_ERROR_CODES
        or SANITIZED_COMMAND_FAILURE_RE.fullmatch(value) is not None
        or any(
            pattern.fullmatch(value) is not None
            for pattern in REPOSITORY_DEFINED_ERROR_CODE_PATTERNS
        )
    )
READINESS_WAIT_REASONS = frozenset(
    {
        "systemd_starting",
        "systemd_state_unavailable",
        "unit_status_unavailable",
        "required_unit_not_active",
        "certificate_timer_not_active",
        "certificate_timer_enablement_unavailable",
        "certificate_service_in_progress",
        "runtime_service_probe_unavailable",
        "runtime_service_set_incomplete",
    }
)
SERVICE_NAMES = ("broker", "manager", "homeassistant")
F4_COMMANDS = {
    "F4_ACTIVATE": ("activate", "--confirm", "START F4 ACTIVATION: YES"),
    "F4_ACCEPT": ("accept-runtime",),
    "F4_PERSISTENCE": ("enable-persistence",),
    "F4_CERT_AUDIT": ("certificate-audit",),
    "F4_CERT_TIMER": ("enable-certificate-timer",),
}


class ProductionExecutorError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _target_host(target: str) -> str:
    value = target.rsplit("@", 1)[-1]
    if not value or ":" in value:
        raise ProductionExecutorError("target_host_invalid")
    return value


def _tcp_port_reachable(host: str, port: int, *, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def target_binding_sha256(expected_host_key_sha256: str) -> str:
    if (
        len(expected_host_key_sha256) != 64
        or any(c not in "0123456789abcdef" for c in expected_host_key_sha256)
    ):
        raise ProductionExecutorError("host_key_sha256_invalid")
    return hashlib.sha256(
        ("ssh-ed25519:" + expected_host_key_sha256).encode("ascii")
    ).hexdigest()


def _private_directory(path: Path) -> Path:
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    metadata = path.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ProductionExecutorError("private_directory_invalid")
    return path


def _atomic_private_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = canonical_json_bytes(document)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(raw)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        os.chmod(path, 0o600)
    finally:
        temp.unlink(missing_ok=True)


def _tar_member_bytes(path: Path, member_name: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ProductionExecutorError("release_artifact_invalid")
    try:
        with tarfile.open(path, "r:*") as bundle:
            matches = [
                member
                for member in bundle.getmembers()
                if member.isfile() and member.name.lstrip("./") == member_name
            ]
            if len(matches) != 1:
                raise ProductionExecutorError(
                    f"release_tar_member_invalid:{member_name}"
                )
            stream = bundle.extractfile(matches[0])
            if stream is None:
                raise ProductionExecutorError(
                    f"release_tar_member_unreadable:{member_name}"
                )
            return stream.read()
    except tarfile.TarError as error:
        raise ProductionExecutorError("release_tar_invalid") from error


def _tar_member_sha256(path: Path, member_name: str) -> str:
    return hashlib.sha256(_tar_member_bytes(path, member_name)).hexdigest()


def _tar_member_text(path: Path, member_name: str) -> str:
    try:
        return _tar_member_bytes(path, member_name).decode("utf-8").strip()
    except UnicodeError as error:
        raise ProductionExecutorError(
            f"release_tar_member_text_invalid:{member_name}"
        ) from error


def _target_failure_record(
    completed: subprocess.CompletedProcess[str],
) -> dict[str, Any] | None:
    for output in (completed.stderr, completed.stdout):
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not lines:
            continue
        try:
            report = json.loads(lines[-1])
        except json.JSONDecodeError:
            continue
        if (
            isinstance(report, dict)
            and report.get("schema") == TARGET_VERIFY_REPORT_SCHEMA
            and report.get("status") == "FAIL"
        ):
            return report
    return None


def _raise_target_failure(stage: str, report: dict[str, Any]) -> None:
    failure_class = report.get("failure_class")
    if failure_class not in {"VERIFY_FAILED", "EVIDENCE_INSUFFICIENT"}:
        raise ProductionExecutorError(f"{stage}_failure_class_invalid")
    error_code = report.get("error_code")
    valid_code = (
        isinstance(error_code, str)
        and _repository_defined_error_code(error_code)
    )
    if failure_class == "EVIDENCE_INSUFFICIENT":
        error = EvidenceInsufficientError(
            f"{stage}_evidence_insufficient"
            if valid_code
            else f"{stage}_error_code_invalid"
        )
    else:
        error = ProductionExecutorError(
            f"{stage}_command_failed"
            if valid_code
            else f"{stage}_error_code_invalid"
        )
    error.target_failure_class = failure_class
    if valid_code:
        error.error_code = error_code
    raise error


def _json_output(completed: subprocess.CompletedProcess[str], stage: str) -> dict[str, Any]:
    if completed.returncode != 0:
        if stage in {"target_local_reboot_verify", "post_reboot_readiness"}:
            report = _target_failure_record(completed)
            if report is not None:
                _raise_target_failure(stage, report)
        if stage == "runtime_snapshot":
            for line in reversed((completed.stderr or "").splitlines()):
                try:
                    report = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if (
                    isinstance(report, dict)
                    and report.get("status") == "FAIL"
                    and report.get("failure_class") == "EVIDENCE_INSUFFICIENT"
                ):
                    raise EvidenceInsufficientError(
                        "runtime_snapshot_evidence_insufficient"
                    )
        raise ProductionExecutorError(f"{stage}_command_failed")
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise ProductionExecutorError(f"{stage}_output_missing")
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise ProductionExecutorError(f"{stage}_output_invalid") from error
    if not isinstance(value, dict):
        raise ProductionExecutorError(f"{stage}_output_invalid")
    return value


def _emit_progress(stage: str, status: str, **fields: object) -> None:
    document = {
        "schema": PROGRESS_SCHEMA,
        "stage": stage,
        "status": status,
        "at": _utc_now(),
        **fields,
    }
    print(
        "PRODUCTION_PROGRESS="
        + json.dumps(document, sort_keys=True, separators=(",", ":")),
        flush=True,
    )


def _wait_for_reboot_arm(run_id: str) -> dict[str, Any]:
    expected = f"{REBOOT_ARM_PREFIX} {run_id}"
    summary = {
        "schema": SCHEMA,
        "run_id": run_id,
        "required_input": expected,
        "input_timeout_seconds": None,
        "post_reboot_password_required": True,
    }
    print(
        "REBOOT_ARMING_SUMMARY="
        + json.dumps(summary, sort_keys=True, separators=(",", ":")),
        flush=True,
    )
    while True:
        try:
            entered = input("REBOOT_ARMING> ")
        except (EOFError, KeyboardInterrupt) as error:
            raise ProductionExecutorError(
                "reboot_operator_arming_input_closed"
            ) from error
        if entered == expected:
            return {
                "status": "PASS",
                "run_id": run_id,
                "operator_present": True,
                "post_reboot_password_expected": True,
            }
        print("REBOOT_ARMING_WAITING=INPUT_NOT_MATCHED", flush=True)


def _mqtt_varint(value: int) -> bytes:
    output = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value:
            digit |= 0x80
        output.append(digit)
        if not value:
            return bytes(output)


def _mqtt_field(value: str) -> bytes:
    payload = value.encode("utf-8")
    if len(payload) > 65535:
        raise ProductionExecutorError("mqtt_field_too_long")
    return len(payload).to_bytes(2, "big") + payload


def _recv_exact(stream: ssl.SSLSocket, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        block = stream.recv(count - len(data))
        if not block:
            raise ProductionExecutorError("mqtt_connection_closed")
        data.extend(block)
    return bytes(data)


def _recv_varint(stream: ssl.SSLSocket) -> int:
    multiplier = 1
    value = 0
    for _ in range(4):
        byte = _recv_exact(stream, 1)[0]
        value += (byte & 0x7F) * multiplier
        if not byte & 0x80:
            if multiplier > 1 and value < multiplier:
                raise ProductionExecutorError("mqtt_remaining_length_noncanonical")
            return value
        multiplier *= 128
    raise ProductionExecutorError("mqtt_remaining_length_invalid")


def _mqtt_rejection_reason(
    host: str,
    *,
    ca_pem: str,
    username: str,
    password: str,
    client_id: str,
) -> int:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cadata=ca_pem)
    raw = socket.create_connection((host, BROKER_TLS_PORT), timeout=8)
    with context.wrap_socket(raw, server_hostname=TLS_SERVER_NAME) as stream:
        stream.settimeout(8)
        flags = 0x02 | 0x80 | 0x40
        variable = (
            b"\x00\x04MQTT"
            + b"\x05"
            + bytes((flags,))
            + b"\x00\x0a"
            + b"\x00"
        )
        payload = (
            _mqtt_field(client_id)
            + _mqtt_field(username)
            + _mqtt_field(password)
        )
        packet = b"\x10" + _mqtt_varint(len(variable) + len(payload)) + variable + payload
        stream.sendall(packet)
        if _recv_exact(stream, 1) != b"\x20":
            raise ProductionExecutorError("mqtt_connack_invalid")
        remaining = _recv_varint(stream)
        # Mosquitto's authentication refusal is exactly flags/reason/zero properties.
        # Other responses, including malformed/truncated packets, are not rejection proof.
        if remaining != 3:
            raise ProductionExecutorError("mqtt_refusal_connack_length_invalid")
        body = _recv_exact(stream, remaining)
        if body[0] != 0 or body[2] != 0 or body[1] not in {0x86, 0x87}:
            raise ProductionExecutorError("mqtt_authentication_refusal_not_proven")
        return body[1]


class LiveProductionAdapter:
    def __init__(
        self,
        *,
        release_root: Path,
        target: str,
        known_hosts: Path,
        expected_host_key_sha256: str,
        run_id: str,
        evidence_root: Path,
        work_root: Path,
    ) -> None:
        self.release_root = release_root.resolve()
        verified = verify_release_directory(self.release_root)
        if verified.get("status") != "PASS":
            raise ProductionExecutorError("release_verification_failed")
        try:
            release = json.loads(
                (self.release_root / "release.json").read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ProductionExecutorError("release_json_invalid") from error
        self.release = validate_release(release)
        self.target = target
        self.host = _target_host(target)
        self.expected_host_key_sha256 = expected_host_key_sha256
        self.run_id = run_id
        self.evidence_root = _private_directory(evidence_root)
        self.work_root = _private_directory(work_root)
        self.transport = SSHTransport(
            target=target,
            known_hosts=known_hosts,
            expected_host_key_sha256=expected_host_key_sha256,
        )
        self.remote_root: str | None = None
        self.reboot_actuated = False
        self.failure_session_closed = False
        self._ca_pem: str | None = None
        self.f4_manifest_sha256 = _tar_member_sha256(
            self._artifact("f4_control"),
            "f4-package/f4-package-manifest.json",
        )
        self.reboot_manifest_sha256 = _tar_member_sha256(
            self._artifact("reboot_control"),
            "reboot-successor-control/reboot-successor-manifest.json",
        )

    def _artifact(self, name: str) -> Path:
        path = self.release_root / "artifacts" / name
        if path.is_symlink() or not path.is_file():
            raise ProductionExecutorError(f"release_artifact_missing:{name}")
        binding = self.release["artifacts"].get(name)
        if (
            not isinstance(binding, dict)
            or binding.get("size_bytes") != path.stat().st_size
            or binding.get("sha256") != _sha256(path)
        ):
            raise ProductionExecutorError(f"release_artifact_binding_invalid:{name}")
        return path

    def _remote(self, argv: tuple[str, ...], *, timeout: float = 300, check: bool = True):
        return self.transport.run_remote(argv, timeout=timeout, check=check)

    def _remote_json(self, argv: tuple[str, ...], stage: str, *, timeout: float = 300):
        return _json_output(
            self._remote(argv, timeout=timeout, check=False),
            stage,
        )

    def _remote_secret_text(self, path: str) -> str:
        completed = self._remote(("sudo", "-n", "cat", path), timeout=30, check=False)
        if completed.returncode != 0:
            raise ProductionExecutorError("remote_secret_read_failed")
        return completed.stdout.rstrip("\r\n")

    def _remote_json_file(self, path: str) -> dict[str, Any]:
        raw = self._remote_secret_text(path)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ProductionExecutorError("remote_json_invalid") from error
        if not isinstance(value, dict):
            raise ProductionExecutorError("remote_json_invalid")
        return value

    def _remote_sha256(self, path: str) -> str:
        completed = self._remote(
            ("sudo", "-n", "sha256sum", path),
            timeout=30,
            check=False,
        )
        fields = completed.stdout.split()
        value = fields[0] if completed.returncode == 0 and fields else ""
        if (
            len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ProductionExecutorError("remote_sha256_failed")
        return value

    def _open_remote_root(self) -> None:
        if self.remote_root is not None:
            raise ProductionExecutorError("remote_workspace_already_open")
        completed = self._remote(
            ("mktemp", "-d", "/var/tmp/n3w-f5-v2-executor.XXXXXX"),
            timeout=30,
            check=False,
        )
        if completed.returncode != 0:
            raise ProductionExecutorError("remote_workspace_create_failed")
        value = completed.stdout.strip()
        if not value.startswith("/var/tmp/n3w-f5-v2-executor."):
            raise ProductionExecutorError("remote_workspace_invalid")
        self.remote_root = value
        self._upload_tool("n3w_t1_production_v2_contract.py")
        self._upload_tool("n3w_t1_production_marker.py")
        self._upload_tool("n3w_t1_fresh_host_baseline.py")

    def _cleanup_remote_root(self) -> None:
        root = self.remote_root
        if root is None:
            return
        completed = self._remote(("rm", "-rf", root), timeout=30, check=False)
        if completed.returncode != 0:
            raise ProductionExecutorError("remote_workspace_cleanup_failed")
        self.remote_root = None

    def _upload_tool(self, name: str) -> str:
        if self.remote_root is None:
            raise ProductionExecutorError("remote_workspace_not_open")
        local = Path(__file__).resolve().parent / name
        remote = f"{self.remote_root}/{name}"
        self.transport.scp_to(local, remote, timeout=180)
        return remote

    def _marker_command(self, command: str, binding: dict[str, str], *extra: str):
        if self.remote_root is None:
            raise ProductionExecutorError("remote_workspace_not_open")
        marker = f"{self.remote_root}/n3w_t1_production_marker.py"
        argv = [
            "sudo",
            "-n",
            "env",
            f"PYTHONPATH={self.remote_root}",
            "python3",
            "-B",
            marker,
            command,
        ]
        for key in (
            "run_id",
            "release_id",
            "release_sha256",
            "source_head",
            "target_binding_sha256",
            "ssh_host_key_sha256",
            "plan_sha256",
        ):
            argv.extend(("--" + key.replace("_", "-"), binding[key]))
        argv.extend(extra)
        return tuple(argv)

    def _stage_release_tar(self, name: str, expected_root: str) -> str:
        if self.remote_root is None:
            raise ProductionExecutorError("remote_workspace_not_open")
        local = self._artifact(name)
        remote_tar = f"{self.remote_root}/{name}.tar"
        self.transport.scp_to(local, remote_tar, timeout=1800)
        completed = self._remote(
            ("tar", "-xf", remote_tar, "-C", self.remote_root),
            timeout=300,
            check=False,
        )
        if completed.returncode != 0:
            raise ProductionExecutorError(f"remote_package_extract_failed:{name}")
        root = f"{self.remote_root}/{expected_root}"
        probe = self._remote(("test", "-d", root), timeout=20, check=False)
        if probe.returncode != 0:
            raise ProductionExecutorError(f"remote_package_root_missing:{name}")
        return root

    def verify_release(self, release: dict[str, Any]) -> dict[str, Any]:
        if validate_release(release) != self.release:
            raise ProductionExecutorError("release_document_mismatch")
        report = verify_release_directory(self.release_root)
        return {"status": "PASS", **report}

    def start_ssh_epoch(self) -> dict[str, Any]:
        epoch = self.transport.start_epoch()
        if epoch.get("host_key_sha256") != self.expected_host_key_sha256:
            raise ProductionExecutorError("ssh_host_key_drift")
        return dict(epoch)

    def qualify(self, release: dict[str, Any]) -> dict[str, Any]:
        result = collect_qualification(self.transport, release)
        if result.get("status") != "PASS":
            raise ProductionExecutorError(
                "fresh_qualification_not_pass:" + str(result.get("status"))
            )
        return result

    def freeze_pre_mutation_failure(
        self,
        failure: dict[str, Any],
    ) -> dict[str, Any]:
        if self.remote_root is not None:
            raise ProductionExecutorError(
                "pre_mutation_remote_workspace_invalid"
            )
        if (
            failure.get("marker_state") != "ABSENT"
            or failure.get("target_mutation") is not False
            or failure.get("reflash_required") is not False
            or failure.get("automatic_retry") is not False
        ):
            raise ProductionExecutorError(
                "pre_mutation_failure_evidence_invalid"
            )
        frozen = freeze_failure(self.evidence_root, failure)
        return {
            "status": "PASS",
            "failure": frozen,
            "evidence_sha256": canonical_sha256(frozen),
            "target_mutation": False,
        }

    def start_marker(self, binding: dict[str, str]) -> dict[str, Any]:
        self._open_remote_root()
        result = self._remote_json(
            self._marker_command(
                "start",
                binding,
                "--created-at",
                _utc_now(),
            ),
            "marker_start",
        )
        if result.get("state") != "STARTED":
            raise ProductionExecutorError("marker_start_not_confirmed")
        return result

    def marker_sha256(self) -> str:
        completed = self._remote(
            ("sudo", "-n", "sha256sum", MARKER_PATH),
            timeout=30,
            check=False,
        )
        if completed.returncode != 0:
            raise ProductionExecutorError("marker_sha256_failed")
        value = completed.stdout.split()[0] if completed.stdout.split() else ""
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ProductionExecutorError("marker_sha256_invalid")
        return value

    def host_baseline(self, packages: dict[str, str]) -> dict[str, Any]:
        _emit_progress("HOST_BASELINE", "STARTED")
        if self.remote_root is None:
            raise ProductionExecutorError("remote_workspace_not_open")
        tool = f"{self.remote_root}/n3w_t1_fresh_host_baseline.py"
        result = self._remote_json(
            (
                "sudo",
                "-n",
                "python3",
                "-B",
                tool,
                "--phase",
                "install",
                "--docker-io-package-version",
                packages["docker.io"],
                "--docker-compose-v2-package-version",
                packages["docker-compose-v2"],
            ),
            "host_baseline",
            timeout=1800,
        )
        if result.get("status") != "PASS":
            raise ProductionExecutorError("host_baseline_not_pass")
        _emit_progress("HOST_BASELINE", "PASS")
        return result

    def f3_deploy(self, run_context: dict[str, str]) -> dict[str, Any]:
        _emit_progress("F3_DEPLOY", "STARTED")
        context = self.work_root / f"run-context-{self.run_id}.json"
        _atomic_private_json(context, run_context)
        payload = self._artifact("f3_payload")
        images = self._artifact("f3_image")
        archive_sha = _tar_member_text(payload, "runtime-payload.sha256").split()[0]
        manifest_sha = _tar_member_text(payload, "payload-manifest.sha256").split()[0]
        command = (
            sys.executable,
            str(Path(__file__).resolve().parent / "n3w_t1_fresh_product_staging_host.py"),
            "--t1",
            self.target,
            "--phase",
            "apply",
            "--release-f3-payload",
            str(payload),
            "--release-f3-images",
            str(images),
            "--archive-sha256",
            archive_sha,
            "--manifest-sha256",
            manifest_sha,
            "--run-context",
            str(context),
        )
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=7200,
            env=self.transport.managed_environment(),
        )
        result = _json_output(completed, "f3_deploy")
        if result.get("status") != "PASS":
            raise ProductionExecutorError("f3_deploy_not_pass")
        _emit_progress("F3_DEPLOY", "PASS")
        return result

    def provision(self) -> dict[str, Any]:
        _emit_progress("PROVISION", "STARTED")
        started = self._remote_json(
            (
                "sudo",
                "-n",
                PROVISION_CLI,
                "start",
                "--confirm",
                "START DEVICE PROVISIONING: YES",
            ),
            "provision_start",
            timeout=1800,
        )
        if started.get("status") != "PASS":
            raise ProductionExecutorError("provision_start_not_pass")
        verified = self._remote_json(
            ("sudo", "-n", PROVISION_CLI, "verify"),
            "provision_verify",
            timeout=600,
        )
        if verified.get("status") != "PASS":
            raise ProductionExecutorError("provision_verify_not_pass")
        _emit_progress("PROVISION", "PASS")
        return {
            "status": "PASS",
            "start_state": started.get("state"),
            "verify_state": verified.get("state"),
            "production_service_start": False,
            "board_access": False,
        }

    def f4_action(self, action: str, authorization_id: str) -> dict[str, Any]:
        _emit_progress(action, "STARTED")
        if action == "F4_PREPARE":
            package_root = self._stage_release_tar("f4_control", "f4-package")
            script = f"{package_root}/tools/n3w_t1_f4_activation_host.py"
            result = self._remote_json(
                (
                    "sudo",
                    "-n",
                    "python3",
                    "-B",
                    script,
                    "prepare",
                    "--confirm",
                    "PREPARE F4 ACTIVATION: YES",
                    "--authorization-id",
                    authorization_id,
                    "--package-root",
                    package_root,
                    "--package-manifest-sha256",
                    self.f4_manifest_sha256,
                    "--package-source-head",
                    self.release["source_head"],
                ),
                "f4_prepare",
                timeout=1200,
            )
        else:
            command = F4_COMMANDS.get(action)
            if command is None:
                raise ProductionExecutorError(f"f4_action_invalid:{action}")
            argv = ["sudo", "-n", F4_CLI, *command, "--authorization-id", authorization_id]
            result = self._remote_json(tuple(argv), action.casefold(), timeout=1200)
        if result.get("status") != "PASS":
            raise ProductionExecutorError(f"{action.casefold()}_not_pass")
        _emit_progress(action, "PASS")
        return result

    def controlled_reboot(
        self,
        install_authorization_id: str,
        reboot_authorization_id: str,
    ) -> dict[str, Any]:
        _emit_progress("REBOOT_CONTROL", "PREPARING")
        package_root = self._stage_release_tar(
            "reboot_control",
            "reboot-successor-control",
        )
        script = f"{package_root}/tools/n3w_t1_f4_reboot_authority.py"
        transaction_sha = self._remote_sha256(
            F4_TRANSACTION_PATH,
        )
        common = (
            "--source-head",
            self.release["source_head"],
            "--manifest-sha256",
            self.reboot_manifest_sha256,
            "--expected-transaction-sha256",
            transaction_sha,
        )
        claim_install = self._remote_json(
            (
                "sudo",
                "-n",
                "python3",
                "-B",
                script,
                "claim-install",
                "--package-root",
                package_root,
                "--authorization-id",
                install_authorization_id,
                *common,
            ),
            "reboot_control_claim_install",
        )
        if claim_install.get("status") != "PASS":
            raise ProductionExecutorError("reboot_control_claim_install_not_pass")
        installed = self._remote_json(
            (
                "sudo",
                "-n",
                "python3",
                "-B",
                script,
                "install-control",
                "--package-root",
                package_root,
                *common,
            ),
            "reboot_control_install",
        )
        if installed.get("status") != "PASS":
            raise ProductionExecutorError("reboot_control_install_not_pass")
        verified = self._remote_json(
            (
                "sudo",
                "-n",
                REBOOT_AUTHORITY_CLI,
                "verify-install",
                *common,
            ),
            "reboot_control_verify",
        )
        if verified.get("status") != "PASS":
            raise ProductionExecutorError("reboot_control_verify_not_pass")
        _emit_progress("REBOOT_CONTROL", "WAITING_FOR_OPERATOR")
        armed = _wait_for_reboot_arm(self.run_id)
        if armed.get("status") != "PASS":
            raise ProductionExecutorError("reboot_operator_arming_not_pass")
        _emit_progress("REBOOT_CONTROL", "ARMED")
        claim = self._remote_json(
            (
                "sudo",
                "-n",
                REBOOT_AUTHORITY_CLI,
                "claim-reboot",
                "--authorization-id",
                reboot_authorization_id,
                *common,
            ),
            "reboot_claim",
        )
        if (
            claim.get("status") != "PASS"
            or claim.get("state") != "REBOOT_PENDING"
            or claim.get("host_reboot_actuation_required") is not True
        ):
            raise ProductionExecutorError("reboot_claim_not_pass")
        verification = self._remote_json(
            (
                "sudo",
                "-n",
                REBOOT_AUTHORITY_CLI,
                "verify-reboot-claim",
                *common,
            ),
            "reboot_claim_verify",
        )
        if verification.get("status") != "PASS":
            raise ProductionExecutorError("reboot_claim_verify_not_pass")
        self._cleanup_remote_root()
        control_path = str(self.transport.control_path)
        self.reboot_actuated = True
        actuation = self._remote(
            ("sudo", "-n", "systemctl", "reboot"),
            timeout=30,
            check=False,
        )
        if actuation.returncode not in {0, 255}:
            raise ProductionExecutorError("reboot_actuation_failed")
        disconnect = self._wait_for_old_boot_ssh_down(control_path)
        _emit_progress("REBOOT_CONTROL", "OLD_BOOT_SSH_DOWN")
        _emit_progress("REBOOT_CONTROL", "REBOOT_PENDING")
        return {
            "status": "PASS",
            "state": "REBOOT_PENDING",
            "reboot_authorization_claimed": True,
            "reboot_authorization_consumed": True,
            "host_reboot_actuation_required": True,
            "control_master_disconnected": disconnect["control_master_disconnected"],
            "ssh_down_observed": disconnect["ssh_down_observed"],
            "board_access": False,
        }

    def _wait_for_old_boot_ssh_down(self, control_path: str) -> dict[str, bool]:
        deadline = time.monotonic() + REBOOT_DISCONNECT_SECONDS
        control_master_disconnected = False
        tcp_down_streak = 0
        while time.monotonic() < deadline:
            if not control_master_disconnected:
                checked = self.transport.runner.run(
                    ("ssh", "-S", control_path, "-O", "check", self.target),
                    timeout=10,
                    check=False,
                )
                control_master_disconnected = checked.returncode != 0
            if _tcp_port_reachable(
                self.host,
                22,
                timeout=REBOOT_TCP_PROBE_TIMEOUT_SECONDS,
            ):
                tcp_down_streak = 0
            else:
                tcp_down_streak += 1
            ssh_down_observed = tcp_down_streak >= REBOOT_TCP_DOWN_CONFIRMATIONS
            if control_master_disconnected and ssh_down_observed:
                return {
                    "control_master_disconnected": True,
                    "ssh_down_observed": True,
                }
            time.sleep(REBOOT_TCP_DOWN_POLL_SECONDS)
        raise ProductionExecutorError("reboot_disconnect_not_observed")

    def close_pre_reboot_epoch(self) -> dict[str, Any]:
        if self.remote_root is not None:
            self._cleanup_remote_root()
        result = self.transport.close_epoch(
            expected_disconnect=self.reboot_actuated,
        )
        self.failure_session_closed = result.get("session_closed") is True
        return dict(result)

    def wait_for_ssh(self) -> dict[str, Any]:
        _emit_progress("WAIT_FOR_SSH", "STARTED")
        deadline = time.monotonic() + SSH_WAIT_SECONDS
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((self.host, 22), timeout=3):
                    _emit_progress("WAIT_FOR_SSH", "PASS")
                    return {
                        "status": "PASS",
                        "ssh_available": True,
                        "wait_seconds_max": SSH_WAIT_SECONDS,
                    }
            except OSError:
                time.sleep(2)
        raise ProductionExecutorError("post_reboot_ssh_timeout")

    def start_post_reboot_epoch(self) -> dict[str, Any]:
        _emit_progress("SSH_EPOCH_2", "PASSWORD_REQUIRED")
        epoch = self.transport.start_post_reboot_epoch()
        if epoch.get("host_key_sha256") != self.expected_host_key_sha256:
            raise ProductionExecutorError("post_reboot_host_key_drift")
        self.reboot_actuated = False
        _emit_progress("SSH_EPOCH_2", "PASS")
        return dict(epoch)

    def wait_for_post_reboot_readiness(self) -> dict[str, Any]:
        started = time.monotonic()
        deadline = started + READINESS_TIMEOUT_SECONDS
        _emit_progress(
            "POST_REBOOT_READINESS",
            "STARTED",
            timeout_seconds=READINESS_TIMEOUT_SECONDS,
            poll_interval_seconds=READINESS_POLL_SECONDS,
        )
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProductionExecutorError("post_reboot_readiness_timeout")
            report = self._remote_json(
                ("sudo", "-n", REBOOT_VERIFY_CLI, "--readiness"),
                "post_reboot_readiness",
                timeout=min(30.0, remaining),
            )
            if (
                report.get("schema") != READINESS_SCHEMA
                or report.get("source_head") != self.release.get("source_head")
                or re.fullmatch(r"[0-9a-f]{40}", str(report.get("source_head"))) is None
                or re.fullmatch(
                    r"[0-9a-f]{64}", str(report.get("control_manifest_sha256"))
                ) is None
                or re.fullmatch(r"[0-9a-f]{64}", str(report.get("boot_id_sha256"))) is None
                or report.get("board_access") is not False
                or report.get("target_mutation") is not False
            ):
                raise ProductionExecutorError("post_reboot_readiness_report_invalid")

            status = report.get("status")
            if status == "PASS":
                if report.get("state") != "READY":
                    raise ProductionExecutorError("post_reboot_readiness_state_invalid")
                _emit_progress(
                    "POST_REBOOT_READINESS",
                    "PASS",
                    elapsed_seconds=round(time.monotonic() - started, 1),
                )
                return report

            reason = report.get("wait_reason")
            if (
                status != "WAIT"
                or report.get("state") != "WAITING_FOR_BOOT_CONVERGENCE"
                or reason not in READINESS_WAIT_REASONS
            ):
                raise ProductionExecutorError("post_reboot_readiness_report_invalid")
            _emit_progress(
                "POST_REBOOT_READINESS",
                "WAITING",
                reason=reason,
                elapsed_seconds=round(time.monotonic() - started, 1),
            )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProductionExecutorError("post_reboot_readiness_timeout")
            time.sleep(min(READINESS_POLL_SECONDS, remaining))

    def read_started_marker(self) -> dict[str, Any]:
        return self._remote_json_file(MARKER_PATH)

    def target_local_reboot_verify(self) -> dict[str, Any]:
        result = self._remote_json(
            ("sudo", "-n", REBOOT_VERIFY_CLI),
            "target_local_reboot_verify",
            timeout=600,
        )
        if result.get("status") != "PASS":
            raise ProductionExecutorError("target_local_reboot_verify_not_pass")
        return result

    def _ca(self) -> str:
        if self._ca_pem is None:
            self._ca_pem = self._remote_secret_text(
                "/etc/n3wfc4/tls/ca.pem"
            )
        return self._ca_pem

    def _tls_probe(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cadata=self._ca())
        raw = socket.create_connection((self.host, BROKER_TLS_PORT), timeout=8)
        with context.wrap_socket(raw, server_hostname=TLS_SERVER_NAME) as stream:
            if not stream.getpeercert():
                raise ProductionExecutorError("tls_peer_certificate_missing")

    def external_probe(self, name: str) -> dict[str, Any]:
        if name == "TCP_8883":
            with socket.create_connection((self.host, BROKER_TLS_PORT), timeout=8):
                pass
        elif name in {"TLS_CA", "TLS_HOSTNAME_SNI"}:
            self._tls_probe()
        elif name == "INVALID_CREDENTIAL_REJECTED":
            # Fresh synthetic values cannot select a production ClientID or password.
            nonce = secrets.token_hex(32)
            reason = _mqtt_rejection_reason(
                self.host,
                ca_pem=self._ca(),
                username="n3w-acceptance-denied-" + nonce,
                password=secrets.token_hex(32),
                client_id="n3w-acceptance-denied-" + nonce,
            )
            return {
                "status": "PASS", "accepted": True, "probe": name,
                "connack_reason": reason,
            }
        elif name == "HOMEASSISTANT_HTTP_READY":
            connection = http.client.HTTPConnection(
                self.host,
                HOMEASSISTANT_PORT,
                timeout=8,
            )
            try:
                connection.request("GET", "/api/")
                response = connection.getresponse()
                response.read(1024)
                if response.status not in {200, 401}:
                    raise ProductionExecutorError(
                        "homeassistant_http_not_ready"
                    )
            finally:
                connection.close()
        else:
            raise ProductionExecutorError(f"external_probe_unknown:{name}")
        return {"status": "PASS", "accepted": True, "probe": name}

    def runtime_snapshot(self) -> dict[str, Any]:
        return self._remote_json(
            ("sudo", "-n", REBOOT_VERIFY_CLI, "--snapshot"),
            "runtime_snapshot",
            timeout=MAX_SAMPLE_GAP_SECONDS,
        )

    def observe_runtime(self, seconds: int, baseline: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        samples = []
        previous = started
        while True:
            snapshot = require_continuity(baseline, self.runtime_snapshot())
            now = time.monotonic()
            if now - previous > MAX_SAMPLE_GAP_SECONDS:
                raise ProductionExecutorError("runtime_observation_coverage_gap")
            samples.append({"elapsed_seconds": now - started, "snapshot": snapshot})
            previous = now
            if now - started >= seconds:
                break
            time.sleep(min(SAMPLE_INTERVAL_SECONDS, seconds - (now - started)))
        return {"status": "PASS", "observation_seconds": seconds, "samples": samples}

    def post_reboot_acceptance(
        self,
        release: dict[str, Any],
        binding: dict[str, str],
    ) -> dict[str, Any]:
        _emit_progress("POST_REBOOT_ACCEPTANCE", "STARTED")
        result = run_acceptance(self, release, binding)
        _emit_progress("POST_REBOOT_ACCEPTANCE", "PASS")
        return result

    def accept_marker(
        self,
        binding: dict[str, str],
        acceptance_sha256: str,
    ) -> dict[str, Any]:
        _emit_progress("MARKER_ACCEPTED", "STARTED")
        self._open_remote_root()
        result = self._remote_json(
            self._marker_command(
                "accept",
                binding,
                "--acceptance-sha256",
                acceptance_sha256,
                "--accepted-at",
                _utc_now(),
            ),
            "marker_accept",
        )
        if (
            result.get("state") != "ACCEPTED"
            or result.get("T1_PRODUCTION_READY") is not True
        ):
            raise ProductionExecutorError("marker_accept_not_confirmed")
        _emit_progress("MARKER_ACCEPTED", "PASS")
        return result

    def close_post_reboot_epoch(self) -> dict[str, Any]:
        if self.remote_root is not None:
            self._cleanup_remote_root()
        result = self.transport.close_epoch()
        self.failure_session_closed = result.get("session_closed") is True
        return dict(result)

    def freeze_failure(self, failure: dict[str, Any]) -> dict[str, Any]:
        frozen = freeze_failure(self.evidence_root, failure)
        return {"status": "PASS", "failure_frozen": True, "failure": frozen}

    def collect_failure_forensics(self) -> dict[str, Any]:
        probes: dict[str, Callable[[], Any]] = {
            "production_marker": lambda: self._remote_json_file(MARKER_PATH),
            "f4_transaction": lambda: self._remote_json_file(F4_TRANSACTION_PATH),
            "reboot_claim": lambda: self._remote_json_file(REBOOT_CLAIM_PATH),
            "system_state": lambda: {
                "systemd": self._remote(
                    ("systemctl", "is-system-running"),
                    timeout=20,
                    check=False,
                ).stdout.strip()
            },
        }
        snapshot = collect_snapshot(self.evidence_root, probes)
        manifest = build_manifest(self.evidence_root)
        return {
            "status": "PASS",
            "evidence_complete": snapshot.get("status") == "COMPLETE",
            "bundle_sha256": manifest["bundle_sha256"],
            "unavailable_count": manifest["unavailable_count"],
        }

    def failure_session_close(self) -> dict[str, Any]:
        try:
            if self.remote_root is not None and not self.reboot_actuated:
                self._cleanup_remote_root()
            result = self.transport.close_epoch(
                expected_disconnect=self.reboot_actuated,
            )
        except Exception as error:
            return {
                "status": "FAIL",
                "session_closed": False,
                "error_code": type(error).__name__,
            }
        self.remote_root = None
        self.failure_session_closed = result.get("session_closed") is True
        return dict(result)

    def record_reflash_disposition(self) -> dict[str, Any]:
        disposition = reflash_disposition(
            self.evidence_root,
            {"session_closed": self.failure_session_closed},
        )
        return {
            "status": "PASS",
            "reflash_required": disposition.get("REFLASH_ALLOWED") is True,
            "bundle_sha256": disposition["bundle_sha256"],
        }


def approval_callback(run_id: str, evidence_root: Path):
    expected = f"{APPROVAL_PREFIX} {run_id}"

    def approve(plan: dict[str, Any]) -> bool:
        _atomic_private_json(evidence_root / "production-plan.json", plan)
        summary = {
            "schema": SCHEMA,
            "run_id": plan["run_id"],
            "release_id": plan["release_id"],
            "release_sha256": plan["release_sha256"],
            "source_head": plan["source_head"],
            "target_binding_sha256": plan["target_binding_sha256"],
            "ssh_host_key_sha256": plan["ssh_host_key_sha256"],
            "actions": plan["actions"],
            "approval_required": expected,
        }
        print(
            "PRODUCTION_APPROVAL_SUMMARY="
            + json.dumps(summary, sort_keys=True, separators=(",", ":")),
            flush=True,
        )
        entered = input("PRODUCTION_APPROVAL> ")
        return entered == expected

    return approve


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--release-root", type=Path, required=True)
    value.add_argument("--target", required=True)
    value.add_argument("--known-hosts", type=Path, required=True)
    value.add_argument("--expected-host-key-sha256", required=True)
    value.add_argument("--run-id")
    value.add_argument("--evidence-root", type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    run_id = args.run_id or secrets.token_hex(32)
    if (
        len(run_id) != 64
        or any(c not in "0123456789abcdef" for c in run_id)
    ):
        print(
            json.dumps(
                {"schema": SCHEMA, "status": "STOP", "error_code": "run_id_invalid"},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    evidence_root = args.evidence_root
    if evidence_root is None:
        evidence_root = (
            Path.home()
            / "Documents"
            / "N3W"
            / "production-runs"
            / run_id
        )
    try:
        evidence_root = _private_directory(evidence_root)
        work_root = Path(tempfile.mkdtemp(prefix="n3w-f5-v2-live."))
        os.chmod(work_root, 0o700)
        adapter = LiveProductionAdapter(
            release_root=args.release_root,
            target=args.target,
            known_hosts=args.known_hosts,
            expected_host_key_sha256=args.expected_host_key_sha256,
            run_id=run_id,
            evidence_root=evidence_root,
            work_root=work_root,
        )
        binding = target_binding_sha256(args.expected_host_key_sha256)
        print(f"RUN_ID={run_id}", flush=True)
        print(f"TARGET_BINDING_SHA256={binding}", flush=True)
        result = R3Orchestrator(adapter).execute(
            adapter.release,
            run_id=run_id,
            target_binding_sha256=binding,
            approved=False,
            approval_callback=approval_callback(run_id, evidence_root),
        )
        _atomic_private_json(evidence_root / "result-private.json", result)
        public = {
            key: result[key]
            for key in (
                "schema",
                "status",
                "release_id",
                "release_sha256",
                "source_head",
                "run_id_sha256",
                "target_binding_sha256",
                "marker_state",
                "error_class",
                "device_acceptance",
                "T1_PRODUCTION_READY",
                "operator_session_closed",
                "evidence_complete",
                "reflash_required",
                "terminal_stage",
                "private_result_sha256",
            )
            if key in result
        }
        _atomic_private_json(evidence_root / "result-public.json", public)
        print(
            "PRODUCTION_RESULT="
            + json.dumps(public, sort_keys=True, separators=(",", ":")),
            flush=True,
        )
        return 0 if (
            result.get("status") == "PASS"
            and result.get("T1_PRODUCTION_READY") is True
        ) else 2
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
    ) as error:
        document = {
            "schema": SCHEMA,
            "status": "STOP",
            "error_code": str(error)[:300] or type(error).__name__,
            "run_id": run_id,
            "board_access": False,
        }
        try:
            _atomic_private_json(evidence_root / "executor-stop.json", document)
        except Exception:
            pass
        print(
            json.dumps(document, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 2
    finally:
        if "work_root" in locals():
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
