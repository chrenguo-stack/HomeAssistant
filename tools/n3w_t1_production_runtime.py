#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import n3w_t1_fresh_product_staging_host as staging
from n3w_t1_production_contract import (
    canonical_sha256,
    phase_artifact_sha256,
    validate_release,
)
from n3w_t1_ssh_transport import SSHTransport, SSHTransportError


FILE_SET_SCHEMA = "gh.n3w-t1-production-file-set/1"
MAC_FILE_SET_SCOPE = "mac_orchestrator"
TARGET_FILE_SET_SCOPE = "target_authority"

MAC_REQUIRED_FILES = frozenset(
    {
        "tools/n3w_t1_production.py",
        "tools/n3w_t1_production_runtime.py",
        "tools/n3w_t1_ssh_transport.py",
        "tools/n3w_t1_production_contract.py",
        "tools/n3w_t1_fresh_product_staging_host.py",
        "tools/n3w_t1_minimal_baseline_readonly_inventory.py",
        (
            "tools/execution_packages/n3w/f2/"
            "t1_fresh_readonly_preflight/executor.py"
        ),
        (
            "tools/execution_packages/n3w/f2/"
            "t1_fresh_readonly_identity/executor.py"
        ),
    }
)

TARGET_REQUIRED_FILES = frozenset(
    {
        "n3w_t1_production_authority.py",
        "n3w_t1_production_contract.py",
        "n3w_t1_fresh_host_baseline.py",
    }
)

F3_ARTIFACT_RELATIVE = Path("artifacts/f3/artifact.zip")
F4_PACKAGE_RELATIVE = Path("artifacts/f4")
REBOOT_PACKAGE_RELATIVE = Path("artifacts/reboot")
MAC_MANIFEST_RELATIVE = Path("artifacts/mac/manifest.json")
TARGET_MANIFEST_RELATIVE = Path("artifacts/target/manifest.json")
TARGET_FILES_RELATIVE = Path("artifacts/target/files")

F4_MANIFEST_NAME = "f4-package-manifest.json"
REBOOT_MANIFEST_NAME = "reboot-successor-manifest.json"

SHA256_RE = re.compile(r"[0-9a-f]{64}")
SOURCE_RE = re.compile(r"[0-9a-f]{40}")


class ProductionRuntimeError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_file(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ProductionRuntimeError(f"json_file_invalid:{path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProductionRuntimeError(
            f"json_file_invalid:{path.name}"
        ) from error
    if not isinstance(value, dict):
        raise ProductionRuntimeError(f"json_file_invalid:{path.name}")
    return value


def _private_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ProductionRuntimeError("runtime_private_record_exists")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ProductionRuntimeError("runtime_private_root_invalid")
    os.chmod(path.parent, 0o700)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    payload = (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _last_json(stdout: str, stderr: str = "") -> dict[str, Any]:
    values: list[dict[str, Any]] = []
    for line in (stdout + "\n" + stderr).splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    if not values:
        raise ProductionRuntimeError("runtime_json_output_missing")
    return values[-1]


def _file_set_manifest(
    manifest_path: Path,
    files_root: Path,
    *,
    expected_scope: str,
    expected_sha256: str,
    source_head: str,
    required_files: frozenset[str],
) -> dict[str, str]:
    if (
        SHA256_RE.fullmatch(expected_sha256) is None
        or _sha256_file(manifest_path) != expected_sha256
    ):
        raise ProductionRuntimeError(
            f"{expected_scope}_manifest_binding_invalid"
        )
    document = _json_file(manifest_path)
    if set(document) != {"schema", "scope", "source_head", "files"}:
        raise ProductionRuntimeError(
            f"{expected_scope}_manifest_fields_invalid"
        )
    if (
        document.get("schema") != FILE_SET_SCHEMA
        or document.get("scope") != expected_scope
        or document.get("source_head") != source_head
    ):
        raise ProductionRuntimeError(
            f"{expected_scope}_manifest_invalid"
        )
    records = document.get("files")
    if not isinstance(records, list):
        raise ProductionRuntimeError(
            f"{expected_scope}_manifest_files_invalid"
        )
    observed: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "path",
            "sha256",
            "size",
        }:
            raise ProductionRuntimeError(
                f"{expected_scope}_manifest_record_invalid"
            )
        relative = record.get("path")
        digest = record.get("sha256")
        size = record.get("size")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(digest, str)
            or SHA256_RE.fullmatch(digest) is None
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
        ):
            raise ProductionRuntimeError(
                f"{expected_scope}_manifest_record_invalid"
            )
        path = files_root / relative
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != size
            or _sha256_file(path) != digest
        ):
            raise ProductionRuntimeError(
                f"{expected_scope}_file_binding_invalid:{relative}"
            )
        if relative in observed:
            raise ProductionRuntimeError(
                f"{expected_scope}_manifest_duplicate_path"
            )
        observed[relative] = digest
    if frozenset(observed) != required_files:
        raise ProductionRuntimeError(
            f"{expected_scope}_file_set_invalid"
        )
    return observed


def _package_manifest(
    root: Path,
    name: str,
    *,
    expected_sha256: str,
    source_head: str,
) -> dict[str, Any]:
    path = root / name
    if (
        root.is_symlink()
        or not root.is_dir()
        or path.is_symlink()
        or not path.is_file()
        or _sha256_file(path) != expected_sha256
    ):
        raise ProductionRuntimeError(
            f"package_manifest_binding_invalid:{name}"
        )
    document = _json_file(path)
    if document.get("source_head") != source_head:
        raise ProductionRuntimeError(
            f"package_source_head_invalid:{name}"
        )
    return document


def _f3_payload_authority_binding(
    artifact: Path,
    target_records: dict[str, str],
) -> None:
    try:
        with zipfile.ZipFile(artifact) as outer:
            baseline = outer.read("host-baseline.py")
            with outer.open("runtime-payload.tar.gz") as stream:
                with tarfile.open(fileobj=stream, mode="r|gz") as bundle:
                    manifest: dict[str, Any] | None = None
                    for member in bundle:
                        if (
                            member.isfile()
                            and member.name.lstrip("./")
                            == "payload-manifest.json"
                        ):
                            source = bundle.extractfile(member)
                            if source is None:
                                break
                            value = json.loads(source.read().decode("utf-8"))
                            if isinstance(value, dict):
                                manifest = value
                            break
    except (
        KeyError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        tarfile.TarError,
        zipfile.BadZipFile,
    ) as error:
        raise ProductionRuntimeError(
            "production_f3_authority_binding_invalid"
        ) from error
    if (
        manifest is None
        or manifest.get("schema")
        != "gh.n3w-t1-fresh-bootstrap-payload/2"
    ):
        raise ProductionRuntimeError(
            "production_f3_authority_binding_invalid"
        )
    records = manifest.get("files")
    if not isinstance(records, list):
        raise ProductionRuntimeError(
            "production_f3_authority_binding_invalid"
        )
    by_path = {
        str(record.get("path")): str(record.get("sha256"))
        for record in records
        if isinstance(record, dict)
    }
    for name in (
        "n3w_t1_production_authority.py",
        "n3w_t1_production_contract.py",
    ):
        expected = target_records[name]
        if (
            by_path.get(f"tools/{name}") != expected
            or by_path.get(
                f"runtime-source/opt/HomeAssistant/tools/{name}"
            )
            != expected
        ):
            raise ProductionRuntimeError(
                f"production_f3_authority_binding_invalid:{name}"
            )
    if (
        hashlib.sha256(baseline).hexdigest()
        != target_records["n3w_t1_fresh_host_baseline.py"]
    ):
        raise ProductionRuntimeError(
            "production_f3_baseline_binding_invalid"
        )


def _target_host(target: str) -> str:
    value = target.rsplit("@", 1)[-1]
    if not value or any(character.isspace() for character in value):
        raise ProductionRuntimeError("target_invalid")
    return value


@contextmanager
def _environment(value: dict[str, str]) -> Iterator[None]:
    previous = os.environ.copy()
    os.environ.clear()
    os.environ.update(value)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


class ProductionRuntimeBackend:
    def __init__(
        self,
        release: dict[str, Any],
        release_path: Path,
        *,
        target: str,
        known_hosts: Path,
        expected_host_key_sha256: str,
        private_record_path: Path | None = None,
        transport: SSHTransport | None = None,
    ) -> None:
        self.release = validate_release(release)
        self.release_path = release_path.resolve()
        self.release_root = self.release_path.parent
        self.source_root = Path(__file__).resolve().parents[1]
        self.target = target
        self.known_hosts = known_hosts
        self.expected_host_key_sha256 = expected_host_key_sha256
        self.f3_artifact = self.release_root / F3_ARTIFACT_RELATIVE
        self.f4_package = self.release_root / F4_PACKAGE_RELATIVE
        self.reboot_package = self.release_root / REBOOT_PACKAGE_RELATIVE
        self.target_files_root = (
            self.release_root / TARGET_FILES_RELATIVE
        )
        self._validate_artifacts()

        base = (
            private_record_path.parent
            if private_record_path is not None
            else Path(tempfile.gettempdir())
        )
        base.mkdir(parents=True, exist_ok=True)
        if base.is_symlink() or not base.is_dir():
            raise ProductionRuntimeError("runtime_work_root_invalid")
        self.work_root = Path(
            tempfile.mkdtemp(prefix=".n3w-f5-runtime.", dir=base)
        )
        os.chmod(self.work_root, 0o700)

        self.transport = transport or SSHTransport(
            target=target,
            known_hosts=known_hosts,
            expected_host_key_sha256=expected_host_key_sha256,
        )
        self.remote_control_dir: str | None = None
        self.remote_f4_package: str | None = None
        self.remote_reboot_package: str | None = None
        self.initial_identity: dict[str, str] | None = None
        self.plan: dict[str, Any] | None = None
        self._f3_installed = False
        self._last_report_sha256: str | None = None
        self._authority_predecessor_sha256: str | None = None
        self._active_context: dict[str, Any] | None = None
        self._active_context_local: Path | None = None
        self._active_context_remote: str | None = None
        self._finalize_result: dict[str, Any] | None = None
        self._reboot_pending_claim_sha256: str | None = None
        self._reboot_control_report: dict[str, Any] | None = None
        self._reboot_control_report_sha256: str | None = None
        self._reboot_command_attempted = False

    def _validate_artifacts(self) -> None:
        artifacts = self.release["artifacts"]
        mac_manifest = self.release_root / MAC_MANIFEST_RELATIVE
        target_manifest = self.release_root / TARGET_MANIFEST_RELATIVE
        _file_set_manifest(
            mac_manifest,
            self.source_root,
            expected_scope=MAC_FILE_SET_SCOPE,
            expected_sha256=artifacts["mac_orchestrator"]["sha256"],
            source_head=self.release["source_head"],
            required_files=MAC_REQUIRED_FILES,
        )
        target_records = _file_set_manifest(
            target_manifest,
            self.target_files_root,
            expected_scope=TARGET_FILE_SET_SCOPE,
            expected_sha256=artifacts["target_authority"]["sha256"],
            source_head=self.release["source_head"],
            required_files=TARGET_REQUIRED_FILES,
        )
        if (
            self.f3_artifact.is_symlink()
            or not self.f3_artifact.is_file()
            or _sha256_file(self.f3_artifact)
            != artifacts["f3_payload"]["sha256"]
        ):
            raise ProductionRuntimeError(
                "f3_payload_release_binding_invalid"
            )
        _package_manifest(
            self.f4_package,
            F4_MANIFEST_NAME,
            expected_sha256=artifacts["f4_control"]["sha256"],
            source_head=self.release["source_head"],
        )
        _package_manifest(
            self.reboot_package,
            REBOOT_MANIFEST_NAME,
            expected_sha256=artifacts["reboot_control"]["sha256"],
            source_head=self.release["source_head"],
        )
        _f3_payload_authority_binding(
            self.f3_artifact,
            target_records,
        )

    def connect_pre_reboot(self) -> dict[str, object]:
        return self.transport.start_epoch()

    def target_identity(self) -> dict[str, str]:
        machine = self.transport.run_remote(
            ("cat", "/etc/machine-id"),
            timeout=30,
        ).stdout.strip()
        key = self.transport.run_remote(
            ("cat", "/etc/ssh/ssh_host_ed25519_key.pub"),
            timeout=30,
        ).stdout.strip().split()
        if not machine or len(key) < 2 or key[0] != "ssh-ed25519":
            raise ProductionRuntimeError("target_identity_invalid")
        try:
            key_blob = base64.b64decode(key[1], validate=True)
        except ValueError as error:
            raise ProductionRuntimeError("target_host_key_invalid") from error
        host_key = hashlib.sha256(key_blob).hexdigest()
        target_binding = hashlib.sha256(
            f"{machine}\n{host_key}\n".encode("utf-8")
        ).hexdigest()
        if host_key != self.expected_host_key_sha256:
            raise ProductionRuntimeError("target_host_key_binding_mismatch")
        identity = {
            "target_binding_sha256": target_binding,
            "ssh_host_key_sha256": host_key,
        }
        if (
            self.initial_identity is not None
            and identity != self.initial_identity
        ):
            raise ProductionRuntimeError("target_identity_drift")
        self.initial_identity = identity
        return identity

    def preflight(
        self,
        *,
        release: dict[str, Any],
        identity: dict[str, str],
    ) -> dict[str, object]:
        if validate_release(release) != self.release:
            raise ProductionRuntimeError("preflight_release_drift")
        if self.initial_identity != identity:
            raise ProductionRuntimeError("preflight_identity_drift")
        evidence = self.work_root / "preflight"
        executor = (
            self.source_root
            / "tools/execution_packages/n3w/f2/"
            "t1_fresh_readonly_preflight/executor.py"
        )
        environment = self.transport.managed_environment(
            os.environ.copy()
        )
        completed = subprocess.run(
            (
                sys.executable,
                str(executor),
                "--execute",
                "--target",
                self.target,
                "--evidence-root",
                str(evidence),
                "--confirm",
                "READONLY N3W T1 FRESH PREFLIGHT: YES",
                "--production-release",
                str(self.release_path),
                "--production-f3-artifact",
                str(self.f3_artifact),
            ),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=1800,
            env=environment,
        )
        report = _last_json(completed.stdout, completed.stderr)
        if completed.returncode != 0 or report.get("status") != "PASS":
            raise ProductionRuntimeError(
                "production_readonly_preflight_failed:"
                + str(report.get("error_code"))[:200]
            )
        return report

    def _remote_mktemp(self, prefix: str) -> str:
        completed = self.transport.run_remote(
            ("mktemp", "-d", f"/var/tmp/{prefix}.XXXXXXXX"),
            timeout=30,
        )
        value = completed.stdout.strip()
        if not value.startswith("/var/tmp/"):
            raise ProductionRuntimeError("remote_mktemp_invalid")
        return value

    def _stage_target_control(self) -> None:
        if self.remote_control_dir is not None:
            return
        remote = self._remote_mktemp("n3w-f5-control")
        for name in sorted(TARGET_REQUIRED_FILES):
            local = self.target_files_root / name
            self.transport.scp_to(local, f"{remote}/{name}")
        self.transport.scp_to(
            self.release_path,
            f"{remote}/approved-release.json",
        )
        self.remote_control_dir = remote

    def _write_and_stage_json(
        self,
        name: str,
        document: dict[str, Any],
    ) -> tuple[Path, str]:
        if self.remote_control_dir is None:
            raise ProductionRuntimeError("remote_control_not_ready")
        local = self.work_root / name
        _private_json(local, document)
        remote = f"{self.remote_control_dir}/{name}"
        self.transport.scp_to(local, remote)
        return local, remote

    def _authority_location(self) -> tuple[str, str]:
        if self._f3_installed:
            return (
                "/opt/HomeAssistant/tools/"
                "n3w_t1_production_authority.py",
                "/opt/HomeAssistant/tools",
            )
        if self.remote_control_dir is None:
            raise ProductionRuntimeError("remote_control_not_ready")
        return (
            f"{self.remote_control_dir}/"
            "n3w_t1_production_authority.py",
            self.remote_control_dir,
        )

    def _remote_json(
        self,
        argv: tuple[str, ...],
        *,
        timeout: float = 600,
        check: bool = True,
    ) -> dict[str, Any]:
        completed = self.transport.run_remote(
            argv,
            timeout=timeout,
            check=False,
        )
        report = _last_json(completed.stdout, completed.stderr)
        if (
            check
            and (
                completed.returncode != 0
                or report.get("status") != "PASS"
            )
        ):
            raise ProductionRuntimeError(
                "remote_command_failed:"
                + str(
                    report.get("error_code")
                    or report.get("reason")
                    or completed.returncode
                )[:220]
            )
        return report

    def _authority(
        self,
        args: tuple[str, ...],
        *,
        timeout: float = 300,
    ) -> dict[str, Any]:
        script, python_path = self._authority_location()
        return self._remote_json(
            (
                "sudo",
                "-n",
                "env",
                f"PYTHONPATH={python_path}",
                "python3",
                script,
                *args,
            ),
            timeout=timeout,
        )

    def approve_run(
        self,
        plan: dict[str, Any],
    ) -> dict[str, object]:
        if self.initial_identity is None:
            raise ProductionRuntimeError("target_identity_not_proven")
        self._stage_target_control()
        self.plan = dict(plan)
        _local, remote_plan = self._write_and_stage_json(
            "production-plan.json",
            plan,
        )
        report = self._authority(
            ("approve", "--plan", remote_plan),
            timeout=120,
        )
        if (
            report.get("state") != "APPROVED"
            or report.get("run_id") != plan["run_id"]
            or report.get("authorization_consumed") is not True
            or report.get("replay_allowed") is not False
        ):
            raise ProductionRuntimeError(
                "target_run_approval_invalid"
            )
        return report

    def _claim_phase(
        self,
        phase: str,
        *,
        plan: dict[str, Any],
        predecessor_sha256: str | None,
    ) -> tuple[dict[str, Any], Path, str]:
        if self.plan != plan:
            raise ProductionRuntimeError("production_plan_drift")
        if predecessor_sha256 != self._last_report_sha256:
            raise ProductionRuntimeError(
                "orchestrator_predecessor_report_drift"
            )
        binding = {
            "source_head": plan["source_head"],
            "release_id": plan["release_id"],
            "artifact_sha256": phase_artifact_sha256(
                self.release,
                phase,
            ),
            "predecessor_sha256": (
                self._authority_predecessor_sha256
            ),
            "target_binding_sha256": plan["target_binding_sha256"],
        }
        _local_binding, remote_binding = self._write_and_stage_json(
            f"{phase.lower()}-binding.json",
            binding,
        )
        claimed = self._authority(
            (
                "claim",
                "--run-id",
                plan["run_id"],
                "--phase",
                phase,
                "--binding",
                remote_binding,
            )
        )
        begun = self._authority(
            (
                "begin",
                "--run-id",
                plan["run_id"],
                "--phase",
                phase,
                "--expected-claim-sha256",
                str(claimed["claim_sha256"]),
            )
        )
        context = self._authority(
            (
                "context",
                "--run-id",
                plan["run_id"],
                "--phase",
                phase,
            )
        )
        if (
            context.get("claim_sha256")
            != begun.get("claim_sha256")
            or context.get("authorization_consumed") is not True
            or context.get("replay_allowed") is not False
        ):
            raise ProductionRuntimeError("phase_context_invalid")
        local_context, remote_context = self._write_and_stage_json(
            f"{phase.lower()}-context.json",
            context,
        )
        self._active_context = context
        self._active_context_local = local_context
        self._active_context_remote = remote_context
        return context, local_context, remote_context

    def _complete_active(
        self,
        phase: str,
        report: dict[str, Any],
    ) -> None:
        if self.plan is None or self._active_context is None:
            raise ProductionRuntimeError("active_phase_missing")
        result_sha256 = canonical_sha256(report)
        completed = self._authority(
            (
                "complete",
                "--run-id",
                self.plan["run_id"],
                "--phase",
                phase,
                "--expected-claim-sha256",
                str(self._active_context["claim_sha256"]),
                "--result-sha256",
                result_sha256,
            )
        )
        if (
            completed.get("state") != "SUCCEEDED"
            or completed.get("result_sha256") != result_sha256
        ):
            raise ProductionRuntimeError(
                "phase_completion_invalid"
            )
        self._authority_predecessor_sha256 = str(
            completed["claim_sha256"]
        )
        self._active_context = None
        self._active_context_local = None
        self._active_context_remote = None

    def _mark_unknown(self, phase: str, error: Exception) -> None:
        if (
            self.plan is None
            or self._active_context is None
        ):
            return
        try:
            self._authority(
                (
                    "fail",
                    "--run-id",
                    self.plan["run_id"],
                    "--phase",
                    phase,
                    "--expected-claim-sha256",
                    str(self._active_context["claim_sha256"]),
                    "--state",
                    "UNKNOWN",
                    "--failure-code",
                    (str(error) or type(error).__name__)[:180],
                ),
                timeout=120,
            )
        except Exception:
            pass

    def _run_target_python(
        self,
        script: str,
        args: tuple[str, ...],
        *,
        python_path: str,
        timeout: float = 1800,
    ) -> dict[str, Any]:
        return self._remote_json(
            (
                "sudo",
                "-n",
                "env",
                f"PYTHONPATH={python_path}",
                "python3",
                script,
                *args,
            ),
            timeout=timeout,
        )

    def _dispatch_host_baseline(
        self,
        remote_context: str,
    ) -> dict[str, Any]:
        if self.remote_control_dir is None:
            raise ProductionRuntimeError("remote_control_not_ready")
        return self._run_target_python(
            (
                f"{self.remote_control_dir}/"
                "n3w_t1_fresh_host_baseline.py"
            ),
            (
                "--phase",
                "production-install",
                "--production-phase-context",
                remote_context,
                "--approved-release",
                f"{self.remote_control_dir}/approved-release.json",
            ),
            python_path=self.remote_control_dir,
            timeout=2400,
        )

    def _dispatch_f3(
        self,
        local_context: Path,
    ) -> dict[str, Any]:
        environment = self.transport.managed_environment(
            os.environ.copy()
        )
        with _environment(environment):
            report = staging.execute_production(
                t1=self.target,
                production_release=self.release_path,
                production_f3_artifact=self.f3_artifact,
                production_phase_context=local_context,
            )
        if report.get("status") != "PASS":
            raise ProductionRuntimeError("f3_deploy_failed")
        self._f3_installed = True
        identity = self._authority(("identity",))
        if (
            self.initial_identity is None
            or identity.get("target_binding_sha256")
            != self.initial_identity["target_binding_sha256"]
            or identity.get("ssh_host_key_sha256")
            != self.initial_identity["ssh_host_key_sha256"]
        ):
            raise ProductionRuntimeError(
                "installed_target_authority_identity_drift"
            )
        return report

    def _dispatch_provision(
        self,
        remote_context: str,
    ) -> dict[str, Any]:
        return self._remote_json(
            (
                "sudo",
                "-n",
                "env",
                "PYTHONPATH=/opt/HomeAssistant/tools",
                "/usr/local/sbin/n3w-t1-provision",
                "start",
                "--production-phase-context",
                remote_context,
            ),
            timeout=1800,
        )

    def _stage_package(
        self,
        local_root: Path,
        prefix: str,
    ) -> str:
        remote_root = self._remote_mktemp(prefix)
        for local in sorted(
            path for path in local_root.rglob("*") if path.is_file()
        ):
            if local.is_symlink():
                raise ProductionRuntimeError(
                    "package_symlink_forbidden"
                )
            relative = local.relative_to(local_root)
            remote = f"{remote_root}/{relative.as_posix()}"
            parent = str(Path(remote).parent)
            mkdir = self.transport.run_remote(
                ("mkdir", "-p", parent),
                timeout=30,
                check=False,
            )
            if mkdir.returncode != 0:
                raise ProductionRuntimeError(
                    "remote_package_parent_create_failed"
                )
            self.transport.scp_to(local, remote)
        return remote_root

    def _ensure_f4_package(self) -> str:
        if self.remote_f4_package is None:
            self.remote_f4_package = self._stage_package(
                self.f4_package,
                "n3w-f5-f4",
            )
        return self.remote_f4_package

    def _ensure_reboot_package(self) -> str:
        if self.remote_reboot_package is None:
            self.remote_reboot_package = self._stage_package(
                self.reboot_package,
                "n3w-f5-reboot",
            )
        return self.remote_reboot_package

    def _dispatch_f4_prepare(
        self,
        remote_context: str,
    ) -> dict[str, Any]:
        root = self._ensure_f4_package()
        manifest_sha = self.release["artifacts"]["f4_control"][
            "sha256"
        ]
        return self._run_target_python(
            f"{root}/tools/n3w_t1_f4_activation_host.py",
            (
                "prepare",
                "--package-root",
                root,
                "--package-manifest-sha256",
                manifest_sha,
                "--package-source-head",
                self.release["source_head"],
                "--production-phase-context",
                remote_context,
            ),
            python_path="/opt/HomeAssistant/tools",
            timeout=1800,
        )

    def _dispatch_f4_installed(
        self,
        command: str,
        remote_context: str,
        *,
        timeout: float = 1800,
    ) -> dict[str, Any]:
        return self._remote_json(
            (
                "sudo",
                "-n",
                "env",
                "PYTHONPATH=/opt/HomeAssistant/tools",
                "/usr/local/sbin/n3w-t1-f4-activation",
                command,
                "--production-phase-context",
                remote_context,
            ),
            timeout=timeout,
        )

    def _dispatch_reboot_control(
        self,
        remote_context: str,
    ) -> dict[str, Any]:
        root = self._ensure_reboot_package()
        report = self._run_target_python(
            f"{root}/tools/n3w_t1_f4_reboot_authority.py",
            (
                "production-reboot-control",
                "--package-root",
                root,
                "--source-head",
                self.release["source_head"],
                "--manifest-sha256",
                self.release["artifacts"]["reboot_control"][
                    "sha256"
                ],
                "--production-phase-context",
                remote_context,
            ),
            python_path="/opt/HomeAssistant/tools",
            timeout=1200,
        )
        pending = report.get("reboot_pending_claim_sha256")
        if (
            not isinstance(pending, str)
            or SHA256_RE.fullmatch(pending) is None
        ):
            raise ProductionRuntimeError(
                "reboot_pending_claim_missing"
            )
        self._reboot_pending_claim_sha256 = pending
        return report

    def _dispatch_finalize(
        self,
        remote_context: str,
    ) -> dict[str, Any]:
        root = self.remote_reboot_package
        if root is None:
            raise ProductionRuntimeError(
                "reboot_package_not_staged"
            )
        exists = self.transport.run_remote(
            (
                "test",
                "-f",
                f"{root}/tools/n3w_t1_f4_reboot_authority.py",
            ),
            timeout=30,
            check=False,
        )
        if exists.returncode != 0:
            raise ProductionRuntimeError(
                "reboot_package_missing_after_reboot"
            )
        report = self._run_target_python(
            f"{root}/tools/n3w_t1_f4_reboot_authority.py",
            (
                "production-finalize",
                "--package-root",
                root,
                "--source-head",
                self.release["source_head"],
                "--manifest-sha256",
                self.release["artifacts"]["reboot_control"][
                    "sha256"
                ],
                "--production-phase-context",
                remote_context,
            ),
            python_path="/opt/HomeAssistant/tools",
            timeout=1800,
        )
        if (
            report.get("state") != "REBOOT_ACCEPTED"
            or report.get("device_acceptance") is not True
        ):
            raise ProductionRuntimeError(
                "production_finalize_not_accepted"
            )
        self._finalize_result = dict(report)
        return report

    def _dispatch_close_run(self) -> dict[str, Any]:
        if (
            self.plan is None
            or self._active_context is None
            or self._finalize_result is None
        ):
            raise ProductionRuntimeError(
                "close_run_prestate_missing"
            )
        _local, remote = self._write_and_stage_json(
            "finalize-result.json",
            self._finalize_result,
        )
        report = self._authority(
            (
                "close-run",
                "--run-id",
                self.plan["run_id"],
                "--expected-claim-sha256",
                str(self._active_context["claim_sha256"]),
                "--finalize-result",
                remote,
            )
        )
        if (
            report.get("target_run_terminal") is not True
            or report.get("target_terminal_state") != "PASS"
            or report.get("device_acceptance") is not True
            or report.get("evidence_complete") is not True
        ):
            raise ProductionRuntimeError(
                "target_close_run_invalid"
            )
        self._authority_predecessor_sha256 = str(
            report["claim_sha256"]
        )
        self._active_context = None
        self._active_context_local = None
        self._active_context_remote = None
        return report

    def execute_phase(
        self,
        phase: str,
        *,
        plan: dict[str, Any],
        predecessor_sha256: str | None,
    ) -> dict[str, object]:
        context, local_context, remote_context = self._claim_phase(
            phase,
            plan=plan,
            predecessor_sha256=predecessor_sha256,
        )
        try:
            if phase == "HOST_BASELINE":
                report = self._dispatch_host_baseline(
                    remote_context
                )
            elif phase == "F3_DEPLOY":
                report = self._dispatch_f3(local_context)
            elif phase == "PROVISION":
                report = self._dispatch_provision(
                    remote_context
                )
            elif phase == "F4_PREPARE":
                report = self._dispatch_f4_prepare(
                    remote_context
                )
            elif phase == "F4_ACTIVATE":
                report = self._dispatch_f4_installed(
                    "activate",
                    remote_context,
                )
            elif phase == "F4_ACCEPT":
                report = self._dispatch_f4_installed(
                    "accept-runtime",
                    remote_context,
                    timeout=2400,
                )
            elif phase == "PERSIST_CERT":
                report = self._dispatch_f4_installed(
                    "persist-cert",
                    remote_context,
                    timeout=2400,
                )
            elif phase == "REBOOT_CONTROL":
                report = self._dispatch_reboot_control(
                    remote_context
                )
            elif phase == "FINALIZE":
                report = self._dispatch_finalize(
                    remote_context
                )
            elif phase == "CLOSE_RUN":
                report = self._dispatch_close_run()
            else:
                raise ProductionRuntimeError(
                    f"unsupported_phase:{phase}"
                )
            if report.get("status") != "PASS":
                raise ProductionRuntimeError(
                    f"phase_report_not_pass:{phase}"
                )

            report_digest = canonical_sha256(report)
            if phase == "REBOOT_CONTROL":
                self._reboot_control_report = dict(report)
                self._reboot_control_report_sha256 = report_digest
            elif phase != "CLOSE_RUN":
                self._complete_active(phase, report)

            self._last_report_sha256 = report_digest
            return report
        except Exception as error:
            self._mark_unknown(phase, error)
            raise ProductionRuntimeError(
                f"phase_execution_failed:{phase}:{str(error)[:220]}"
            ) from error

    def transition_reboot(self) -> dict[str, object]:
        if (
            self.plan is None
            or self._active_context is None
            or self._active_context.get("phase") != "REBOOT_CONTROL"
            or self._active_context_remote is None
            or self._reboot_pending_claim_sha256 is None
            or self._reboot_control_report is None
            or self._reboot_control_report_sha256 is None
            or self.remote_reboot_package is None
        ):
            raise ProductionRuntimeError(
                "reboot_transition_prestate_invalid"
            )
        actuation = self._run_target_python(
            (
                f"{self.remote_reboot_package}/tools/"
                "n3w_t1_f4_reboot_authority.py"
            ),
            (
                "claim-production-reboot-actuation",
                "--production-phase-context",
                self._active_context_remote,
                "--expected-pending-claim-sha256",
                self._reboot_pending_claim_sha256,
            ),
            python_path="/opt/HomeAssistant/tools",
            timeout=120,
        )
        if (
            actuation.get("state") != "REBOOT_ACTUATION_CLAIMED"
            or actuation.get("reboot_actuation_attempted") is not True
            or actuation.get("reboot_actuation_replay_allowed") is not False
            or actuation.get("reboot_executed") is not False
        ):
            raise ProductionRuntimeError(
                "reboot_actuation_claim_invalid"
            )

        self._complete_active(
            "REBOOT_CONTROL",
            self._reboot_control_report,
        )
        self._reboot_command_attempted = True
        try:
            completed = self.transport.run_remote(
                ("sudo", "-n", "systemctl", "reboot"),
                timeout=20,
                check=False,
            )
            return {
                "status": "PASS",
                "reboot_command_attempted": True,
                "remote_returncode": completed.returncode,
                "replay_allowed": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "PASS",
                "reboot_command_attempted": True,
                "remote_returncode": None,
                "replay_allowed": False,
            }
        except SSHTransportError as error:
            raise ProductionRuntimeError(
                "reboot_command_not_dispatched"
            ) from error

    def _wait_master_gone(self, timeout: float = 120.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self.transport.assert_master()
            except SSHTransportError:
                return
            time.sleep(1.0)
        raise ProductionRuntimeError(
            "pre_reboot_ssh_master_still_active"
        )

    def _wait_ssh_socket(self, timeout: float = 300.0) -> None:
        host = _target_host(self.target)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(
                    (host, 22),
                    timeout=2.0,
                ):
                    return
            except OSError:
                time.sleep(2.0)
        raise ProductionRuntimeError(
            "post_reboot_ssh_not_reachable"
        )

    def connect_post_reboot(self) -> dict[str, object]:
        if not self._reboot_command_attempted:
            raise ProductionRuntimeError(
                "post_reboot_connection_without_actuation"
            )
        self._wait_master_gone()
        self.transport.close_epoch(expected_disconnect=True)
        self._wait_ssh_socket()
        report = self.transport.start_epoch()
        identity = self.target_identity()
        if identity != self.initial_identity:
            raise ProductionRuntimeError(
                "post_reboot_target_identity_drift"
            )
        self.remote_control_dir = self._remote_mktemp(
            "n3w-f5-post-reboot"
        )
        return report

    def close_session(self) -> dict[str, object]:
        cleanup_ok = True
        remote_paths = [
            path
            for path in (
                self.remote_f4_package,
                self.remote_reboot_package,
                self.remote_control_dir,
            )
            if path is not None
        ]
        if remote_paths:
            try:
                removed = self.transport.run_remote(
                    ("rm", "-rf", "--", *remote_paths),
                    timeout=120,
                    check=False,
                )
                cleanup_ok = removed.returncode == 0
            except Exception:
                cleanup_ok = False
        try:
            closed = self.transport.close_epoch()
            session_closed = (
                cleanup_ok
                and closed.get("status") == "PASS"
                and closed.get("session_closed") is True
            )
        except Exception:
            session_closed = False
        return {
            "status": "PASS" if session_closed else "FAIL",
            "session_closed": session_closed,
            "runtime_private_evidence_root": str(self.work_root),
        }


def _private_setting(name: str, prompt: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    entered = input(prompt).strip()
    if not entered:
        raise ProductionRuntimeError(
            f"private_setting_missing:{name}"
        )
    return entered


def create_backend(
    release: dict[str, Any],
    release_path: Path,
    *,
    private_record_path: Path | None = None,
) -> ProductionRuntimeBackend:
    target = _private_setting(
        "N3W_T1_PRODUCTION_TARGET",
        "T1 target (user@host): ",
    )
    known_hosts = Path(
        _private_setting(
            "N3W_T1_PRODUCTION_KNOWN_HOSTS",
            "Trusted known_hosts file: ",
        )
    ).expanduser()
    host_key = _private_setting(
        "N3W_T1_PRODUCTION_HOST_KEY_SHA256",
        "Trusted SSH host-key SHA-256 (hex): ",
    )
    if SHA256_RE.fullmatch(host_key) is None:
        raise ProductionRuntimeError(
            "trusted_host_key_sha256_invalid"
        )
    return ProductionRuntimeBackend(
        release,
        release_path,
        target=target,
        known_hosts=known_hosts,
        expected_host_key_sha256=host_key,
        private_record_path=private_record_path,
    )
