from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

PLAN_SCHEMA = "gh.m2.t1-manager-identity-host-replica-plan/1"
TRANSACTION_SCHEMA = "gh.m2.t1-manager-identity-host-replica-transaction/1"
MATRIX_SCHEMA = "gh.m2.t1-manager-identity-host-replica-fault-matrix/1"
MARKER_SCHEMA = "gh.m2.t1-manager-identity-host-replica/1"
PREPARATION_SCHEMA = "gh.m2.t1-manager-identity-migration-preparation/1"
RUNTIME_SCHEMA = "gh.m2.t1-manager-runtime-binding/1"

FAULT_PHASES = (
    "after_password_write",
    "after_env_write",
    "after_overlay_write",
    "after_recreate",
    "after_identity",
    "after_subscription",
    "after_canonical_publish",
    "after_discovery_publish",
    "after_reconnect",
    "postactivation",
    "rollback_incomplete",
)

_EXPECTED_RECORDS = {
    "material/manager/manager.env": True,
    "material/manager/password": True,
    "material/manager/compose-secret-fragment.yaml": True,
    "manager-runtime-binding.json": True,
    "transaction-plan.json": False,
    "operator-runbook.txt": False,
}
_MANAGER_KEYS = {
    "GH_MQTT_USERNAME",
    "GH_MQTT_PASSWORD_FILE",
    "GH_MQTT_CLIENT_ID",
}


class ReplicaManagerDriver(Protocol):
    def recreate_manager(
        self,
        *,
        environment_file: Path,
        password_file: Path,
        overlay_file: Path,
    ) -> None: ...

    def verify_authenticated_identity(self, username: str, client_id: str) -> None: ...

    def verify_ingress_subscription(self) -> None: ...

    def verify_canonical_publication(self) -> None: ...

    def verify_discovery_publication(self) -> None: ...

    def verify_reconnect(self) -> None: ...

    def postactivation_audit(self) -> dict[str, object]: ...

    def recreate_after_rollback(self) -> None: ...

    def verify_legacy_anonymous_path(self) -> None: ...


DriverFactory = Callable[[Path], ReplicaManagerDriver]


class ManagerIdentityHostReplicaError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))[:16]


def _private_directory(path: Path, label: str) -> None:
    if (
        not path.is_dir()
        or path.is_symlink()
        or path.stat().st_mode & 0o077
    ):
        raise ManagerIdentityHostReplicaError(
            f"{label} is missing, unsafe, or not private"
        )


def _private_file(path: Path, label: str) -> None:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerIdentityHostReplicaError(
            f"{label} is missing, unsafe, or not mode 0600"
        )


def _read_json(path: Path, label: str) -> dict[str, Any]:
    _private_file(path, label)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerIdentityHostReplicaError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerIdentityHostReplicaError(f"{label} must be an object")
    return document


def _read_key_values(path: Path, label: str) -> dict[str, str]:
    _private_file(path, label)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeError as error:
        raise ManagerIdentityHostReplicaError(f"{label} is not UTF-8") from error
    values: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key or key in values:
            raise ManagerIdentityHostReplicaError(f"{label} contains invalid entries")
        values[key] = value
    return values


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ManagerIdentityHostReplicaError(f"{label} path is missing")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ManagerIdentityHostReplicaError(f"{label} path is unsafe")
    return relative


def _tree_inventory(root: Path) -> tuple[tuple[str, int, str], ...]:
    _private_directory(root, "manager replica tree")
    records: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ManagerIdentityHostReplicaError(
                "manager replica contains a symbolic link"
            )
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            records.append((relative + "/", path.stat().st_mode & 0o777, "directory"))
        elif path.is_file():
            records.append((relative, path.stat().st_mode & 0o777, _sha_path(path)))
        else:
            raise ManagerIdentityHostReplicaError(
                "manager replica contains an unsupported entry"
            )
    return tuple(records)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, payload: bytes, mode: int) -> None:
    if path.exists() and path.is_symlink():
        raise ManagerIdentityHostReplicaError("atomic write target is a symbolic link")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _verify_records(root: Path, manifest: Mapping[str, Any]) -> dict[str, Path]:
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ManagerIdentityHostReplicaError(
            "manager preparation record inventory is missing"
        )
    paths: dict[str, Path] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ManagerIdentityHostReplicaError(
                "manager preparation record inventory is invalid"
            )
        raw = record.get("path")
        relative = _safe_relative(raw, "manager preparation record")
        key = relative.as_posix()
        if key in paths or key not in _EXPECTED_RECORDS:
            raise ManagerIdentityHostReplicaError(
                "manager preparation record inventory is unexpected"
            )
        path = root.joinpath(*relative.parts)
        _private_file(path, f"manager preparation record {key}")
        if (
            record.get("size") != path.stat().st_size
            or record.get("sha256") != _sha_path(path)
            or record.get("contains_secret") is not _EXPECTED_RECORDS[key]
        ):
            raise ManagerIdentityHostReplicaError(
                f"manager preparation record verification failed: {key}"
            )
        paths[key] = path
    if set(paths) != set(_EXPECTED_RECORDS):
        raise ManagerIdentityHostReplicaError(
            "manager preparation record inventory is incomplete"
        )
    return paths


def _validated_preparation(
    preparation_directory: str | Path,
) -> tuple[Path, dict[str, Any], dict[str, Path], dict[str, Any], dict[str, str]]:
    root = Path(preparation_directory).expanduser().resolve()
    if not root.name.startswith("greenhouse-manager-migration-preparation-"):
        raise ManagerIdentityHostReplicaError(
            "manager preparation directory name is not allowed"
        )
    _private_directory(root, "manager preparation directory")
    manifest = _read_json(root / "manifest.json", "manager preparation manifest")
    required = {
        "schema": PREPARATION_SCHEMA,
        "read_only_live_services": True,
        "current_services_modified": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "ready_for_manager_migration_authorization": True,
        "ready_for_manager_migration_apply": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if manifest.get(field) != expected:
            raise ManagerIdentityHostReplicaError(
                f"manager preparation safety flag failed: {field}"
            )
    paths = _verify_records(root, manifest)
    runtime = _read_json(paths["manager-runtime-binding.json"], "manager runtime binding")
    if (
        runtime.get("schema") != RUNTIME_SCHEMA
        or runtime.get("read_only_capture") is not True
        or runtime.get("current_services_modified") is not False
    ):
        raise ManagerIdentityHostReplicaError("manager runtime binding is unsafe")
    values = _read_key_values(
        paths["material/manager/manager.env"],
        "manager environment material",
    )
    if set(values) != _MANAGER_KEYS:
        raise ManagerIdentityHostReplicaError(
            "manager environment material has an unexpected key set"
        )
    password = paths["material/manager/password"].read_text(encoding="utf-8").rstrip(
        "\r\n"
    )
    if not password or "\n" in password or "\r" in password or "\x00" in password:
        raise ManagerIdentityHostReplicaError("manager password material is invalid")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ManagerIdentityHostReplicaError("manager preparation bindings are missing")
    if (
        bindings.get("manager_runtime_binding_sha256")
        != _sha_path(paths["manager-runtime-binding.json"])
        or bindings.get("manager_username_fingerprint")
        != _fingerprint(values["GH_MQTT_USERNAME"])
        or bindings.get("manager_client_id_fingerprint")
        != _fingerprint(values["GH_MQTT_CLIENT_ID"])
    ):
        raise ManagerIdentityHostReplicaError(
            "manager preparation identity binding is invalid"
        )
    return root, manifest, paths, runtime, values


def _replica_paths(
    replica_root: Path,
    *,
    preparation_manifest_sha256: str,
    runtime: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> tuple[Path, Path]:
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if replica_root.is_symlink():
        raise ManagerIdentityHostReplicaError("manager replica root is unsafe")
    root = replica_root.resolve()
    if not root.is_relative_to(temporary_root):
        raise ManagerIdentityHostReplicaError(
            "manager replica root must remain inside the system temporary directory"
        )
    _private_directory(root, "manager replica root")
    marker = _read_json(root / ".gh-m2-manager-host-replica.json", "manager replica marker")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ManagerIdentityHostReplicaError("manager preparation bindings are missing")
    if (
        marker.get("schema") != MARKER_SCHEMA
        or marker.get("replica_only") is not True
        or marker.get("preparation_manifest_sha256") != preparation_manifest_sha256
        or marker.get("manager_runtime_fingerprint")
        != bindings.get("manager_runtime_fingerprint")
        or marker.get("compose_binding_fingerprint")
        != bindings.get("compose_binding_fingerprint")
    ):
        raise ManagerIdentityHostReplicaError("manager replica marker binding is invalid")
    manager_root = root / "manager"
    compose_root = manager_root / "compose"
    secret_root = manager_root / "secrets"
    _private_directory(manager_root, "manager replica live root")
    _private_directory(compose_root, "manager replica Compose root")
    _private_directory(secret_root, "manager replica secret root")
    compose = runtime.get("compose")
    if not isinstance(compose, dict):
        raise ManagerIdentityHostReplicaError("manager Compose runtime binding is missing")
    raw_files = compose.get("config_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ManagerIdentityHostReplicaError("manager Compose file binding is missing")
    names: set[str] = set()
    for record in raw_files:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ManagerIdentityHostReplicaError("manager Compose file binding is invalid")
        name = Path(record["path"]).name
        if not name or name in names:
            raise ManagerIdentityHostReplicaError(
                "manager Compose replica basename binding is ambiguous"
            )
        names.add(name)
        replica = compose_root / name
        if (
            not replica.is_file()
            or replica.is_symlink()
            or replica.stat().st_mode & 0o777 != record.get("mode")
            or replica.stat().st_size != record.get("size")
            or _sha_path(replica) != record.get("sha256")
        ):
            raise ManagerIdentityHostReplicaError(
                f"manager Compose replica baseline drifted: {name}"
            )
    environment = compose.get("environment")
    env_replica = compose_root / ".env"
    if environment is None:
        if env_replica.exists():
            raise ManagerIdentityHostReplicaError(
                "manager Compose replica has an unexpected environment file"
            )
    elif (
        not isinstance(environment, dict)
        or not env_replica.is_file()
        or env_replica.is_symlink()
        or env_replica.stat().st_mode & 0o777 != environment.get("mode")
        or env_replica.stat().st_size != environment.get("size")
        or _sha_path(env_replica) != environment.get("sha256")
    ):
        raise ManagerIdentityHostReplicaError(
            "manager Compose replica environment baseline drifted"
        )
    forbidden = (
        compose_root / "manager-auth.env",
        compose_root / "docker-compose.manager-auth.yml",
        secret_root / "manager/password",
    )
    if any(path.exists() for path in forbidden):
        raise ManagerIdentityHostReplicaError(
            "manager replica already contains authentication mutation state"
        )
    return manager_root, compose_root


def build_manager_host_replica_plan(
    preparation_directory: str | Path,
    replica_root: str | Path,
) -> dict[str, object]:
    root, manifest, paths, runtime, values = _validated_preparation(
        preparation_directory
    )
    manifest_sha = _sha_path(root / "manifest.json")
    manager_root, compose_root = _replica_paths(
        Path(replica_root).expanduser(),
        preparation_manifest_sha256=manifest_sha,
        runtime=runtime,
        manifest=manifest,
    )
    plan: dict[str, object] = {
        "schema": PLAN_SCHEMA,
        "preparation_manifest_sha256": manifest_sha,
        "runtime_binding_sha256": _sha_path(paths["manager-runtime-binding.json"]),
        "manager_material_sha256": {
            relative: _sha_path(path)
            for relative, path in sorted(paths.items())
            if relative.startswith("material/manager/")
        },
        "manager_username_fingerprint": _fingerprint(values["GH_MQTT_USERNAME"]),
        "manager_client_id_fingerprint": _fingerprint(values["GH_MQTT_CLIENT_ID"]),
        "replica_binding": {
            "root_fingerprint": _fingerprint(str(Path(replica_root).resolve())),
            "manager_root_fingerprint": _fingerprint(str(manager_root.resolve())),
            "compose_root_fingerprint": _fingerprint(str(compose_root.resolve())),
        },
        "fault_phases": list(FAULT_PHASES),
        "replica_transaction_ready": True,
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "authorization_required_for_real_t1": True,
        "authorization_claimed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    plan["plan_sha256"] = _sha_bytes(_canonical_json(plan).encode("utf-8"))
    return plan


class ManagerHostReplicaTransactionAdapters:
    def __init__(
        self,
        preparation_directory: str | Path,
        replica_root: str | Path,
        *,
        driver: ReplicaManagerDriver,
        fault_phase: str | None = None,
    ) -> None:
        if fault_phase is not None and fault_phase not in FAULT_PHASES:
            raise ValueError("unsupported manager replica fault phase")
        self.preparation = Path(preparation_directory).expanduser().resolve()
        self.replica_root = Path(replica_root).expanduser().resolve()
        self.driver = driver
        self.fault_phase = fault_phase
        self.plan: dict[str, object] | None = None
        self.workspace: Path | None = None
        self.baseline: Path | None = None
        self.baseline_inventory: tuple[tuple[str, int, str], ...] | None = None
        self.material_paths: dict[str, Path] | None = None
        self.values: dict[str, str] | None = None
        self.mutation_started = False

    def __enter__(self) -> ManagerHostReplicaTransactionAdapters:
        self.prepare()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _phase(self, phase: str) -> None:
        if self.fault_phase == phase:
            raise ManagerIdentityHostReplicaError(
                f"injected manager replica transaction fault: {phase}"
            )

    def prepare(self) -> None:
        if self.workspace is not None:
            return
        root, _manifest, paths, _runtime, values = _validated_preparation(
            self.preparation
        )
        self.plan = build_manager_host_replica_plan(root, self.replica_root)
        self.material_paths = paths
        self.values = values
        workspace = Path(
            tempfile.mkdtemp(
                prefix=".gh-m2-manager-replica-transaction-",
                dir=self.replica_root,
            )
        )
        workspace.chmod(0o700)
        baseline = workspace / "baseline"
        shutil.copytree(
            self.replica_root / "manager",
            baseline / "manager",
            copy_function=shutil.copy2,
        )
        self.workspace = workspace
        self.baseline = baseline
        self.baseline_inventory = _tree_inventory(baseline / "manager")

    def close(self) -> None:
        if self.workspace is not None:
            shutil.rmtree(self.workspace, ignore_errors=True)
            self.workspace = None
            self.baseline = None

    def mutation_executor(self) -> dict[str, object]:
        self.prepare()
        if self.material_paths is None or self.values is None:
            raise ManagerIdentityHostReplicaError(
                "manager replica adapters are not prepared"
            )
        compose_root = self.replica_root / "manager/compose"
        password_file = self.replica_root / "manager/secrets/manager/password"
        environment_file = compose_root / "manager-auth.env"
        overlay_file = compose_root / "docker-compose.manager-auth.yml"
        self.mutation_started = True
        _atomic_write(
            password_file,
            self.material_paths["material/manager/password"].read_bytes(),
            0o600,
        )
        self._phase("after_password_write")
        _atomic_write(
            environment_file,
            self.material_paths["material/manager/manager.env"].read_bytes(),
            0o600,
        )
        self._phase("after_env_write")
        _atomic_write(
            overlay_file,
            self.material_paths[
                "material/manager/compose-secret-fragment.yaml"
            ].read_bytes(),
            0o600,
        )
        self._phase("after_overlay_write")
        self.driver.recreate_manager(
            environment_file=environment_file,
            password_file=password_file,
            overlay_file=overlay_file,
        )
        self._phase("after_recreate")
        self.driver.verify_authenticated_identity(
            self.values["GH_MQTT_USERNAME"],
            self.values["GH_MQTT_CLIENT_ID"],
        )
        self._phase("after_identity")
        self.driver.verify_ingress_subscription()
        self._phase("after_subscription")
        self.driver.verify_canonical_publication()
        self._phase("after_canonical_publish")
        self.driver.verify_discovery_publication()
        self._phase("after_discovery_publish")
        self.driver.verify_reconnect()
        self._phase("after_reconnect")
        return {
            "mutation_started": True,
            "password_written_atomically": True,
            "environment_written_atomically": True,
            "overlay_written_atomically": True,
            "file_and_directory_fsync_completed": True,
            "manager_recreate_requested": True,
            "authenticated_identity_verified": True,
            "ingress_subscription_verified": True,
            "canonical_publication_verified": True,
            "discovery_publication_verified": True,
            "reconnect_verified": True,
            "replica_only": True,
            "current_services_modified": False,
        }

    def postactivation_auditor(self) -> dict[str, object]:
        report = self.driver.postactivation_audit()
        required = {
            "manager_identity_verified": True,
            "ingress_subscription_verified": True,
            "canonical_publication_verified": True,
            "discovery_publication_verified": True,
            "reconnect_verified": True,
            "rollback_required": False,
            "replica_only": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }
        for field, expected in required.items():
            if report.get(field) is not expected:
                raise ManagerIdentityHostReplicaError(
                    f"manager replica postactivation audit failed: {field}"
                )
        self._phase("postactivation")
        return report

    def rollback_executor(self) -> dict[str, object]:
        self.prepare()
        if self.baseline is None or self.baseline_inventory is None or self.workspace is None:
            raise ManagerIdentityHostReplicaError(
                "manager replica rollback baseline is unavailable"
            )
        if self.fault_phase == "rollback_incomplete":
            raise ManagerIdentityHostReplicaError(
                "injected manager replica rollback failure"
            )
        current = self.replica_root / "manager"
        restore = self.workspace / "restore-manager"
        quarantine = self.workspace / "quarantine-manager"
        shutil.copytree(
            self.baseline / "manager",
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
        self.driver.recreate_after_rollback()
        self.driver.verify_legacy_anonymous_path()
        if _tree_inventory(current) != self.baseline_inventory:
            raise ManagerIdentityHostReplicaError(
                "manager replica rollback inventory does not match baseline"
            )
        return {
            "rollback_completed": True,
            "complete_snapshot_inventory_restored": True,
            "manager_auth_material_absent": True,
            "legacy_anonymous_path_verified": True,
            "replica_only": True,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }


def run_manager_host_replica_transaction(
    preparation_directory: str | Path,
    replica_root: str | Path,
    *,
    driver: ReplicaManagerDriver,
    fault_phase: str | None = None,
) -> dict[str, object]:
    mutation: dict[str, object] | None = None
    postactivation: dict[str, object] | None = None
    rollback: dict[str, object] | None = None
    transaction_error: Exception | None = None
    rollback_error: Exception | None = None
    with ManagerHostReplicaTransactionAdapters(
        preparation_directory,
        replica_root,
        driver=driver,
        fault_phase=fault_phase,
    ) as adapters:
        try:
            mutation = adapters.mutation_executor()
            postactivation = adapters.postactivation_auditor()
            if fault_phase is not None:
                raise ManagerIdentityHostReplicaError(
                    "manager replica fault injection did not trigger"
                )
        except Exception as error:
            transaction_error = error
            if adapters.mutation_started:
                try:
                    rollback = adapters.rollback_executor()
                except Exception as after_rollback:
                    rollback_error = after_rollback
    if rollback_error is not None:
        raise ManagerIdentityHostReplicaError(
            "manager replica transaction failed and rollback failed"
        ) from rollback_error
    if transaction_error is not None and rollback is None:
        raise ManagerIdentityHostReplicaError(
            "manager replica transaction failed without verified rollback"
        ) from transaction_error
    return {
        "schema": TRANSACTION_SCHEMA,
        "fault_phase": fault_phase,
        "fault_injected": fault_phase is not None,
        "mutation_completed": mutation is not None,
        "postactivation_verified": (
            postactivation is not None
            and postactivation.get("manager_identity_verified") is True
        ),
        "rollback_completed": (
            rollback is not None and rollback.get("rollback_completed") is True
        ),
        "manager_identity_migrated_in_replica": (
            fault_phase is None and postactivation is not None
        ),
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "authorization_claimed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def run_manager_host_replica_fault_matrix(
    preparation_directory: str | Path,
    replica_template: str | Path,
    *,
    driver_factory: DriverFactory,
) -> dict[str, object]:
    template = Path(replica_template).expanduser().resolve()
    _private_directory(template, "manager replica template")
    template_inventory = _tree_inventory(template)
    results: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="gh-m2-manager-fault-matrix-") as temporary:
        matrix_root = Path(temporary)
        success_root = matrix_root / "success"
        shutil.copytree(template, success_root, copy_function=shutil.copy2)
        success = run_manager_host_replica_transaction(
            preparation_directory,
            success_root,
            driver=driver_factory(success_root),
        )
        if (
            success.get("postactivation_verified") is not True
            or success.get("rollback_completed") is not False
        ):
            raise ManagerIdentityHostReplicaError(
                "manager replica success rehearsal did not complete"
            )
        results["success"] = True
        for phase in FAULT_PHASES:
            candidate = matrix_root / phase
            shutil.copytree(template, candidate, copy_function=shutil.copy2)
            if phase == "rollback_incomplete":
                try:
                    run_manager_host_replica_transaction(
                        preparation_directory,
                        candidate,
                        driver=driver_factory(candidate),
                        fault_phase=phase,
                    )
                except ManagerIdentityHostReplicaError as error:
                    results[phase] = "rollback_failure_explicit" in str(error) or (
                        "rollback failed" in str(error)
                    )
                else:
                    raise ManagerIdentityHostReplicaError(
                        "manager replica incomplete rollback was not reported"
                    )
                continue
            report = run_manager_host_replica_transaction(
                preparation_directory,
                candidate,
                driver=driver_factory(candidate),
                fault_phase=phase,
            )
            if report.get("rollback_completed") is not True:
                raise ManagerIdentityHostReplicaError(
                    f"manager replica fault did not roll back: {phase}"
                )
            if _tree_inventory(candidate) != template_inventory:
                raise ManagerIdentityHostReplicaError(
                    f"manager replica rollback changed baseline: {phase}"
                )
            results[phase] = True
    if _tree_inventory(template) != template_inventory:
        raise ManagerIdentityHostReplicaError(
            "manager replica template changed during fault matrix"
        )
    return {
        "schema": MATRIX_SCHEMA,
        "success_rehearsal_passed": results.get("success") is True,
        "fault_results": results,
        "fault_phase_count": len(FAULT_PHASES),
        "all_faults_exercised": all(results.get(phase) is True for phase in FAULT_PHASES),
        "rollback_failure_reported_explicitly": (
            results.get("rollback_incomplete") is True
        ),
        "template_immutable": True,
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a disabled plan for manager identity migration testing on a marked "
            "temporary host replica."
        )
    )
    parser.add_argument("preparation_directory")
    parser.add_argument("replica_root")
    args = parser.parse_args(argv)
    try:
        report = build_manager_host_replica_plan(
            args.preparation_directory,
            args.replica_root,
        )
    except (
        ManagerIdentityHostReplicaError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 manager host replica plan failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
