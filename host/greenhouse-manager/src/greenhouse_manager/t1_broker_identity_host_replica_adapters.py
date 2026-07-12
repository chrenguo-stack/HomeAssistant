from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from .t1_broker_identity_production_adapter_skeleton import (
    BrokerIdentityProductionAdapterSkeletonError,
    verify_production_adapter_skeleton,
)
from .t1_broker_identity_production_executor_contract import (
    BrokerIdentityProductionExecutorContractError,
    verify_production_executor_contract,
)
from .t1_shadow import (
    PLUGIN_CONFIG_LINE,
    PLUGIN_LINE,
    PLUGIN_PASSWORD_INIT_LINE,
)

PLAN_SCHEMA = "gh.m2.t1-broker-identity-host-replica-plan/1"
TRANSACTION_SCHEMA = "gh.m2.t1-broker-identity-host-replica-transaction/1"
MARKER_SCHEMA = "gh.m2.t1-broker-identity-host-replica/1"

ContractVerifier = Callable[[dict[str, object]], dict[str, object]]
SkeletonVerifier = Callable[[dict[str, object]], dict[str, object]]

FAULT_PHASES = (
    "after_config_replace",
    "after_secret_replace",
    "after_restart",
    "after_state_wait",
    "after_request",
    "after_provisioning",
    "after_bootstrap_delete",
    "postactivation",
    "rollback_incomplete",
)


class ReplicaBrokerDriver(Protocol):
    def restart_mosquitto(self) -> None: ...

    def wait_for_dynamic_security_state(self) -> None: ...

    def apply_exact_request(self, request: dict[str, Any]) -> None: ...

    def verify_provisioning_identity(self) -> None: ...

    def delete_bootstrap_admin(self) -> None: ...

    def postactivation_audit(self) -> dict[str, object]: ...

    def restart_after_rollback(self) -> None: ...

    def verify_anonymous_retained_state(self) -> None: ...


class BrokerIdentityHostReplicaError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityHostReplicaError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityHostReplicaError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise BrokerIdentityHostReplicaError(f"{label} must be a JSON object")
    return document


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise BrokerIdentityHostReplicaError(f"{label} path is missing")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise BrokerIdentityHostReplicaError(f"{label} path is unsafe")
    return path


def _private_directory(path: Path, label: str) -> None:
    if (
        not path.is_dir()
        or path.is_symlink()
        or path.stat().st_mode & 0o077
    ):
        raise BrokerIdentityHostReplicaError(
            f"{label} is missing, unsafe, or not private"
        )


def _tree_inventory(root: Path) -> tuple[tuple[str, int, str], ...]:
    records: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BrokerIdentityHostReplicaError(
                "host replica contains a symbolic link"
            )
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            records.append((relative + "/", path.stat().st_mode & 0o777, "directory"))
        elif path.is_file():
            records.append((relative, path.stat().st_mode & 0o777, _sha256_path(path)))
        else:
            raise BrokerIdentityHostReplicaError(
                "host replica contains an unsupported filesystem entry"
            )
    return tuple(records)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, payload: bytes, mode: int) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _active_lines(value: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in value.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _validate_contract_and_skeleton(
    contract: dict[str, object],
    skeleton: dict[str, object],
    *,
    contract_verifier: ContractVerifier,
    skeleton_verifier: SkeletonVerifier,
) -> tuple[str, str]:
    contract_result = contract_verifier(contract)
    skeleton_result = skeleton_verifier(skeleton)
    if contract_result.get("verified") is not True:
        raise BrokerIdentityHostReplicaError(
            "production executor contract verification is incomplete"
        )
    if skeleton_result.get("verified") is not True:
        raise BrokerIdentityHostReplicaError(
            "production adapter skeleton verification is incomplete"
        )
    contract_sha = contract_result.get("contract_sha256")
    skeleton_contract_sha = skeleton.get("contract_sha256")
    mount_sha = skeleton.get("mount_binding_sha256")
    if (
        not isinstance(contract_sha, str)
        or skeleton_contract_sha != contract_sha
        or not isinstance(mount_sha, str)
        or len(contract_sha) != 64
        or len(mount_sha) != 64
    ):
        raise BrokerIdentityHostReplicaError(
            "production adapter skeleton binding is incomplete"
        )
    required = {
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if skeleton.get(field) is not expected:
            raise BrokerIdentityHostReplicaError(
                f"production adapter skeleton safety flag failed: {field}"
            )
    return contract_sha, mount_sha


def _validate_material_bindings(
    contract: dict[str, object],
    handoff: Path,
) -> dict[str, Path]:
    raw_bindings = contract.get("material_bindings")
    if not isinstance(raw_bindings, list) or not raw_bindings:
        raise BrokerIdentityHostReplicaError(
            "production executor contract material bindings are missing"
        )
    paths: dict[str, Path] = {}
    for raw in raw_bindings:
        if not isinstance(raw, dict):
            raise BrokerIdentityHostReplicaError(
                "production executor material binding is invalid"
            )
        relative = _safe_relative(raw.get("path"), "material binding")
        path = handoff.joinpath(*relative.parts)
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_mode & 0o777 != 0o600
        ):
            raise BrokerIdentityHostReplicaError(
                "production executor material file is missing or unsafe"
            )
        if raw.get("sha256") != _sha256_path(path):
            raise BrokerIdentityHostReplicaError(
                "production executor material fingerprint has drifted"
            )
        paths[relative.as_posix()] = path
    required = {
        "material/broker/dynsec-request.json",
        "material/broker/mosquitto-plugin.conf",
        "material/bootstrap/dynsec-password-init",
    }
    if not required.issubset(paths):
        raise BrokerIdentityHostReplicaError(
            "host replica transaction material is incomplete"
        )
    plugin = _active_lines(
        paths["material/broker/mosquitto-plugin.conf"].read_text(encoding="utf-8")
    )
    if plugin != (
        PLUGIN_LINE,
        PLUGIN_CONFIG_LINE,
        PLUGIN_PASSWORD_INIT_LINE,
    ):
        raise BrokerIdentityHostReplicaError(
            "host replica plugin material is not canonical"
        )
    return paths


def _validate_replica_root(
    root: Path,
    *,
    contract_sha256: str,
    mount_binding_sha256: str,
    expected_config_sha256: str,
) -> tuple[Path, Path]:
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if root.is_symlink():
        raise BrokerIdentityHostReplicaError("host replica root is unsafe")
    root = root.resolve()
    if not root.is_relative_to(temporary_root):
        raise BrokerIdentityHostReplicaError(
            "host replica root must remain inside the system temporary directory"
        )
    _private_directory(root, "host replica root")
    marker = _read_private_json(
        root / ".gh-m2-host-replica.json",
        "host replica marker",
    )
    if (
        marker.get("schema") != MARKER_SCHEMA
        or marker.get("replica_only") is not True
        or marker.get("contract_sha256") != contract_sha256
        or marker.get("mount_binding_sha256") != mount_binding_sha256
    ):
        raise BrokerIdentityHostReplicaError(
            "host replica marker binding is invalid"
        )
    config_dir = root / "mosquitto/config"
    data_dir = root / "mosquitto/data"
    _private_directory(config_dir, "host replica Mosquitto config directory")
    _private_directory(data_dir, "host replica Mosquitto data directory")
    config = config_dir / "mosquitto.conf"
    if not config.is_file() or config.is_symlink():
        raise BrokerIdentityHostReplicaError(
            "host replica mosquitto.conf is missing or unsafe"
        )
    if _sha256_path(config) != expected_config_sha256:
        raise BrokerIdentityHostReplicaError(
            "host replica Broker baseline does not match the contract"
        )
    if (data_dir / "dynamic-security.json").exists():
        raise BrokerIdentityHostReplicaError(
            "host replica already contains Dynamic Security state"
        )
    return config_dir, data_dir


def build_host_replica_plan(
    contract_file: str | Path,
    skeleton_file: str | Path,
    handoff_directory: str | Path,
    replica_root: str | Path,
    *,
    contract_verifier: ContractVerifier = verify_production_executor_contract,
    skeleton_verifier: SkeletonVerifier = verify_production_adapter_skeleton,
) -> dict[str, object]:
    contract_path = Path(contract_file).expanduser().resolve()
    skeleton_path = Path(skeleton_file).expanduser().resolve()
    handoff = Path(handoff_directory).expanduser().resolve()
    root = Path(replica_root).expanduser()
    contract = _read_private_json(contract_path, "production executor contract")
    skeleton = _read_private_json(skeleton_path, "production adapter skeleton")
    contract_sha, mount_sha = _validate_contract_and_skeleton(
        contract,
        skeleton,
        contract_verifier=contract_verifier,
        skeleton_verifier=skeleton_verifier,
    )
    if not handoff.is_dir() or handoff.is_symlink():
        raise BrokerIdentityHostReplicaError(
            "activation handoff directory is missing or unsafe"
        )
    materials = _validate_material_bindings(contract, handoff)
    source_binding = contract.get("source_binding")
    expected_config_sha = (
        source_binding.get("baseline_broker_config_sha256")
        if isinstance(source_binding, dict)
        else None
    )
    if not isinstance(expected_config_sha, str) or len(expected_config_sha) != 64:
        raise BrokerIdentityHostReplicaError(
            "production executor Broker baseline binding is missing"
        )
    config_dir, data_dir = _validate_replica_root(
        root,
        contract_sha256=contract_sha,
        mount_binding_sha256=mount_sha,
        expected_config_sha256=expected_config_sha,
    )
    plan: dict[str, object] = {
        "schema": PLAN_SCHEMA,
        "contract_sha256": contract_sha,
        "mount_binding_sha256": mount_sha,
        "replica_binding": {
            "root_fingerprint": _sha256_text(str(root.resolve()))[:16],
            "config_fingerprint": _sha256_text(str(config_dir.resolve()))[:16],
            "data_fingerprint": _sha256_text(str(data_dir.resolve()))[:16],
            "baseline_config_sha256": expected_config_sha,
        },
        "material_sha256": {
            relative: _sha256_path(path)
            for relative, path in sorted(materials.items())
        },
        "fault_phases": list(FAULT_PHASES),
        "replica_transaction_ready": True,
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    plan["plan_sha256"] = _sha256_bytes(_canonical_json(plan).encode("utf-8"))
    return plan


class HostReplicaTransactionAdapters:
    def __init__(
        self,
        contract_file: str | Path,
        skeleton_file: str | Path,
        handoff_directory: str | Path,
        replica_root: str | Path,
        *,
        driver: ReplicaBrokerDriver,
        fault_phase: str | None = None,
        contract_verifier: ContractVerifier = verify_production_executor_contract,
        skeleton_verifier: SkeletonVerifier = verify_production_adapter_skeleton,
    ) -> None:
        if fault_phase is not None and fault_phase not in FAULT_PHASES:
            raise ValueError("unsupported host replica fault phase")
        self.contract_file = Path(contract_file).expanduser().resolve()
        self.skeleton_file = Path(skeleton_file).expanduser().resolve()
        self.handoff = Path(handoff_directory).expanduser().resolve()
        self.replica_root = Path(replica_root).expanduser().resolve()
        self.driver = driver
        self.fault_phase = fault_phase
        self.contract_verifier = contract_verifier
        self.skeleton_verifier = skeleton_verifier
        self.plan: dict[str, object] | None = None
        self.workspace: Path | None = None
        self.baseline: Path | None = None
        self.mutation_started = False
        self.baseline_inventory: tuple[tuple[str, int, str], ...] | None = None

    def __enter__(self) -> HostReplicaTransactionAdapters:
        self.prepare()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _phase(self, phase: str) -> None:
        if self.fault_phase == phase:
            raise BrokerIdentityHostReplicaError(
                f"injected host replica transaction fault: {phase}"
            )

    def prepare(self) -> None:
        if self.workspace is not None:
            return
        self.plan = build_host_replica_plan(
            self.contract_file,
            self.skeleton_file,
            self.handoff,
            self.replica_root,
            contract_verifier=self.contract_verifier,
            skeleton_verifier=self.skeleton_verifier,
        )
        workspace = Path(
            tempfile.mkdtemp(
                prefix=".gh-m2-host-replica-transaction-",
                dir=self.replica_root,
            )
        )
        workspace.chmod(0o700)
        baseline = workspace / "baseline"
        shutil.copytree(
            self.replica_root / "mosquitto",
            baseline / "mosquitto",
            copy_function=shutil.copy2,
        )
        self.workspace = workspace
        self.baseline = baseline
        self.baseline_inventory = _tree_inventory(baseline / "mosquitto")

    def close(self) -> None:
        if self.workspace is not None:
            shutil.rmtree(self.workspace, ignore_errors=True)
            self.workspace = None
            self.baseline = None

    def mutation_executor(self) -> dict[str, object]:
        self.prepare()
        contract = _read_private_json(
            self.contract_file,
            "production executor contract",
        )
        materials = _validate_material_bindings(contract, self.handoff)
        config_path = self.replica_root / "mosquitto/config/mosquitto.conf"
        secret_path = self.replica_root / "mosquitto/config/dynsec-password-init"
        plugin_path = materials["material/broker/mosquitto-plugin.conf"]
        request_path = materials["material/broker/dynsec-request.json"]
        password_path = materials["material/bootstrap/dynsec-password-init"]

        original = config_path.read_text(encoding="utf-8")
        plugin_lines = _active_lines(plugin_path.read_text(encoding="utf-8"))
        if any(line in _active_lines(original) for line in plugin_lines):
            raise BrokerIdentityHostReplicaError(
                "host replica Broker configuration is already mutated"
            )
        mutated = original.rstrip("\n") + "\n" + "\n".join(plugin_lines) + "\n"
        self.mutation_started = True
        _atomic_write(
            config_path,
            mutated.encode("utf-8"),
            config_path.stat().st_mode & 0o777,
        )
        self._phase("after_config_replace")
        _atomic_write(secret_path, password_path.read_bytes(), 0o600)
        self._phase("after_secret_replace")

        self.driver.restart_mosquitto()
        self._phase("after_restart")
        self.driver.wait_for_dynamic_security_state()
        self._phase("after_state_wait")
        request = _read_private_json(request_path, "Dynamic Security request")
        self.driver.apply_exact_request(request)
        self._phase("after_request")
        self.driver.verify_provisioning_identity()
        self._phase("after_provisioning")
        self.driver.delete_bootstrap_admin()
        self._phase("after_bootstrap_delete")
        return {
            "mutation_started": True,
            "config_replaced_atomically": True,
            "bootstrap_secret_replaced_atomically": True,
            "file_and_directory_fsync_completed": True,
            "mosquitto_restart_requested": True,
            "exact_request_applied": True,
            "provisioning_identity_verified": True,
            "bootstrap_admin_removed": True,
            "replica_only": True,
            "current_services_modified": False,
        }

    def postactivation_auditor(self) -> dict[str, object]:
        report = self.driver.postactivation_audit()
        required = {
            "activation_verified": True,
            "rollback_required": False,
            "broker_identity_activated": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }
        for field, expected in required.items():
            if report.get(field) is not expected:
                raise BrokerIdentityHostReplicaError(
                    f"host replica postactivation audit failed: {field}"
                )
        self._phase("postactivation")
        return report

    def rollback_executor(self) -> dict[str, object]:
        self.prepare()
        if self.baseline is None or self.baseline_inventory is None:
            raise BrokerIdentityHostReplicaError(
                "host replica rollback baseline is unavailable"
            )
        if self.fault_phase == "rollback_incomplete":
            raise BrokerIdentityHostReplicaError(
                "injected host replica rollback failure"
            )
        current = self.replica_root / "mosquitto"
        restore = self.workspace / "restore-mosquitto"
        quarantine = self.workspace / "quarantine-mosquitto"
        shutil.copytree(
            self.baseline / "mosquitto",
            restore,
            copy_function=shutil.copy2,
        )
        os.replace(current, quarantine)
        try:
            os.replace(restore, current)
            _fsync_directory(self.replica_root)
        except Exception:
            if not current.exists() and quarantine.exists():
                os.replace(quarantine, current)
                _fsync_directory(self.replica_root)
            raise
        shutil.rmtree(quarantine)
        self.driver.restart_after_rollback()
        self.driver.verify_anonymous_retained_state()
        restored_inventory = _tree_inventory(current)
        if restored_inventory != self.baseline_inventory:
            raise BrokerIdentityHostReplicaError(
                "host replica rollback inventory does not match the baseline"
            )
        return {
            "rollback_completed": True,
            "complete_snapshot_inventory_restored": True,
            "dynamic_security_state_absent": True,
            "anonymous_retained_state_readable": True,
            "replica_only": True,
            "current_services_modified": False,
        }


def run_host_replica_transaction(
    contract_file: str | Path,
    skeleton_file: str | Path,
    handoff_directory: str | Path,
    replica_root: str | Path,
    *,
    driver: ReplicaBrokerDriver,
    fault_phase: str | None = None,
    contract_verifier: ContractVerifier = verify_production_executor_contract,
    skeleton_verifier: SkeletonVerifier = verify_production_adapter_skeleton,
) -> dict[str, object]:
    mutation: dict[str, object] | None = None
    postactivation: dict[str, object] | None = None
    rollback: dict[str, object] | None = None
    transaction_error: Exception | None = None
    rollback_error: Exception | None = None
    with HostReplicaTransactionAdapters(
        contract_file,
        skeleton_file,
        handoff_directory,
        replica_root,
        driver=driver,
        fault_phase=fault_phase,
        contract_verifier=contract_verifier,
        skeleton_verifier=skeleton_verifier,
    ) as adapters:
        try:
            mutation = adapters.mutation_executor()
            postactivation = adapters.postactivation_auditor()
            if fault_phase is not None:
                raise BrokerIdentityHostReplicaError(
                    "host replica fault injection did not trigger"
                )
        except Exception as error:
            transaction_error = error
            if adapters.mutation_started:
                try:
                    rollback = adapters.rollback_executor()
                except Exception as after_rollback:
                    rollback_error = after_rollback

    if rollback_error is not None:
        raise BrokerIdentityHostReplicaError(
            "host replica transaction failed and rollback failed"
        ) from rollback_error
    if transaction_error is not None and rollback is None:
        raise BrokerIdentityHostReplicaError(
            "host replica transaction failed without verified rollback"
        ) from transaction_error

    fault_injected = fault_phase is not None
    return {
        "schema": TRANSACTION_SCHEMA,
        "fault_phase": fault_phase,
        "fault_injected": fault_injected,
        "mutation_completed": mutation is not None,
        "postactivation_verified": (
            postactivation is not None
            and postactivation.get("activation_verified") is True
        ),
        "rollback_completed": (
            rollback is not None and rollback.get("rollback_completed") is True
        ),
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only plan for atomic Broker adapter testing on a "
            "marked temporary host replica."
        )
    )
    parser.add_argument("contract_file")
    parser.add_argument("skeleton_file")
    parser.add_argument("handoff_directory")
    parser.add_argument("replica_root")
    args = parser.parse_args(argv)
    try:
        report = build_host_replica_plan(
            args.contract_file,
            args.skeleton_file,
            args.handoff_directory,
            args.replica_root,
        )
    except (
        BrokerIdentityHostReplicaError,
        BrokerIdentityProductionAdapterSkeletonError,
        BrokerIdentityProductionExecutorContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker host replica plan failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
