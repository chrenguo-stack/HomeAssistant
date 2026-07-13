from __future__ import annotations

import hashlib
import json
import os
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from .t1_manager_identity_migration_execution_preparation import (
    verify_manager_identity_execution_preparation,
)
from .t1_manager_identity_migration_execution_preparation_common import (
    ManagerIdentityExecutionPreparationError,
    verify_rollback_archive,
)
from .t1_manager_identity_migration_host_replica_adapters import (
    ManagerIdentityHostReplicaError,
    _validated_preparation,
)
from .t1_manager_identity_migration_production_driver_contract import (
    ManagerIdentityProductionDriverContractError,
    verify_manager_production_driver_contract,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

SCHEMA = "gh.m2.t1-manager-identity-production-host-adapters/1"
SNAPSHOT_SCHEMA = "gh.m2.t1-manager-identity-production-snapshot/1"
_AUTH_ENV_NAME = "manager-auth.env"
_OVERLAY_NAME = "docker-compose.manager-auth.yml"


class ManagerProductionHostAdaptersError(RuntimeError):
    pass


class ManagerRuntimeProbe(Protocol):
    def verify_authenticated_identity(self, username: str, client_id: str) -> None: ...

    def verify_ingress_subscription(self) -> None: ...

    def verify_canonical_publication(self) -> None: ...

    def verify_availability_publication(self) -> None: ...

    def verify_discovery_publication(self) -> None: ...

    def verify_reconnect(self) -> None: ...

    def verify_existing_entities(self) -> None: ...

    def postactivation_audit(self) -> dict[str, object]: ...

    def verify_legacy_anonymous_path(self) -> None: ...


class ManagerProductionDriver(Protocol):
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

    def verify_availability_publication(self) -> None: ...

    def verify_discovery_publication(self) -> None: ...

    def verify_reconnect(self) -> None: ...

    def verify_existing_entities(self) -> None: ...

    def postactivation_audit(self) -> dict[str, object]: ...

    def recreate_after_rollback(self) -> None: ...

    def verify_legacy_anonymous_path(self) -> None: ...


@dataclass(frozen=True)
class ManagerHostBinding:
    project: str
    working_dir: Path
    config_files: tuple[Path, ...]
    environment_file: Path | None
    secret_root: Path
    password_target: Path
    auth_environment_target: Path
    overlay_target: Path
    material_environment: Path
    material_password: Path
    material_overlay: Path
    username: str
    client_id: str


@dataclass(frozen=True)
class SnapshotRecord:
    source: Path
    snapshot: Path
    mode: int
    uid: int
    gid: int
    sha256: str


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _private_file(path: Path, label: str) -> Path:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerProductionHostAdaptersError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    return path


def _private_directory(path: Path, label: str) -> Path:
    if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ManagerProductionHostAdaptersError(
            f"{label} is missing, unsafe, or not private"
        )
    return path


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    _private_file(path, label)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerProductionHostAdaptersError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerProductionHostAdaptersError(f"{label} must be a JSON object")
    return document


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_private_parent(path: Path, boundary: Path) -> None:
    if not path.is_relative_to(boundary):
        raise ManagerProductionHostAdaptersError("write target escaped its bound root")
    pending: list[Path] = []
    cursor = path.parent
    while not cursor.exists():
        if cursor == boundary.parent:
            raise ManagerProductionHostAdaptersError("write target escaped its bound root")
        pending.append(cursor)
        cursor = cursor.parent
    if cursor.is_symlink() or not cursor.is_dir():
        raise ManagerProductionHostAdaptersError("write target parent is unsafe")
    for directory in reversed(pending):
        directory.mkdir(mode=0o700)
        _fsync_directory(directory.parent)
    for directory in (path.parent, *path.parent.parents):
        if directory == boundary.parent:
            break
        if directory.is_symlink() or not directory.is_dir():
            raise ManagerProductionHostAdaptersError("write target parent is unsafe")


def _atomic_write(
    path: Path,
    payload: bytes,
    *,
    mode: int,
    uid: int,
    gid: int,
    boundary: Path,
) -> None:
    if path.exists() and path.is_symlink():
        raise ManagerProductionHostAdaptersError("atomic write target cannot be a symlink")
    _ensure_private_parent(path, boundary)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, mode)
        if os.geteuid() == 0:
            os.chown(temporary_path, uid, gid)
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _unlink(path: Path, *, boundary: Path) -> None:
    if not path.is_relative_to(boundary):
        raise ManagerProductionHostAdaptersError("unlink target escaped its bound root")
    if path.is_symlink():
        raise ManagerProductionHostAdaptersError("unlink target cannot be a symlink")
    if path.exists():
        if not path.is_file():
            raise ManagerProductionHostAdaptersError("unlink target must be a regular file")
        path.unlink()
        _fsync_directory(path.parent)


def _absolute_directory(value: object, label: str) -> Path:
    if not isinstance(value, str):
        raise ManagerProductionHostAdaptersError(f"{label} is missing")
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ManagerProductionHostAdaptersError(f"{label} is missing or unsafe")
    return path.resolve()


def _absolute_file(value: object, label: str) -> Path:
    if not isinstance(value, str):
        raise ManagerProductionHostAdaptersError(f"{label} is missing")
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ManagerProductionHostAdaptersError(f"{label} is missing or unsafe")
    return path.resolve()


def _absolute_target(value: object, label: str) -> Path:
    if not isinstance(value, str):
        raise ManagerProductionHostAdaptersError(f"{label} is missing")
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise ManagerProductionHostAdaptersError(f"{label} is unsafe")
    return path.resolve(strict=False)


def _verify_bound_file(path: Path, record: Mapping[str, Any], label: str) -> None:
    stat = path.stat()
    if (
        stat.st_mode & 0o777 != record.get("mode")
        or stat.st_uid != record.get("uid")
        or stat.st_gid != record.get("gid")
        or stat.st_size != record.get("size")
        or _sha_path(path) != record.get("sha256")
    ):
        raise ManagerProductionHostAdaptersError(f"{label} metadata has drifted")


def _read_material_values(path: Path) -> dict[str, str]:
    _private_file(path, "manager environment material")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key or key in values:
            raise ManagerProductionHostAdaptersError(
                "manager environment material contains invalid entries"
            )
        values[key] = value
    expected = {
        "GH_MQTT_USERNAME",
        "GH_MQTT_PASSWORD_FILE",
        "GH_MQTT_CLIENT_ID",
    }
    if set(values) != expected:
        raise ManagerProductionHostAdaptersError(
            "manager environment material has an unexpected key set"
        )
    return values


def _load_binding(
    driver_contract_file: Path,
    execution_preparation_directory: Path,
    preparation_directory: Path,
    *,
    now: datetime | None,
) -> tuple[ManagerHostBinding, dict[str, Any], dict[str, Any]]:
    driver_document = _read_private_json(driver_contract_file, "manager driver contract")
    try:
        driver_verified = verify_manager_production_driver_contract(driver_document)
    except ManagerIdentityProductionDriverContractError as error:
        raise ManagerProductionHostAdaptersError(
            "manager production driver contract is invalid"
        ) from error
    if driver_verified.get("verified") is not True:
        raise ManagerProductionHostAdaptersError(
            "manager production driver contract verification is incomplete"
        )

    try:
        execution_verified = verify_manager_identity_execution_preparation(
            execution_preparation_directory,
            now=now,
            require_fresh=True,
        )
    except ManagerIdentityExecutionPreparationError as error:
        raise ManagerProductionHostAdaptersError(
            "fresh manager execution preparation is invalid"
        ) from error
    if execution_verified.get("verified") is not True:
        raise ManagerProductionHostAdaptersError(
            "fresh manager execution preparation verification is incomplete"
        )

    try:
        prep_root, prep_manifest, prep_paths, runtime, values = _validated_preparation(
            preparation_directory
        )
    except ManagerIdentityHostReplicaError as error:
        raise ManagerProductionHostAdaptersError(
            "manager migration preparation is invalid"
        ) from error

    execution_manifest = _read_private_json(
        execution_preparation_directory / "manifest.json",
        "manager execution preparation manifest",
    )
    bindings = execution_manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ManagerProductionHostAdaptersError(
            "manager execution preparation bindings are missing"
        )
    expected_bindings = {
        "driver_contract_sha256": driver_document.get("driver_contract_sha256"),
        "adapter_contract_sha256": driver_document.get("adapter_contract_sha256"),
        "runtime_binding_sha256": _sha_path(prep_paths["manager-runtime-binding.json"]),
        "preparation_manifest_sha256": _sha_path(prep_root / "manifest.json"),
    }
    for field, expected in expected_bindings.items():
        if bindings.get(field) != expected:
            raise ManagerProductionHostAdaptersError(
                f"manager execution preparation binding failed: {field}"
            )

    compose = runtime.get("compose")
    if not isinstance(compose, dict):
        raise ManagerProductionHostAdaptersError("manager Compose binding is missing")
    project = compose.get("project")
    if not isinstance(project, str) or not project or any(
        character.isspace() for character in project
    ):
        raise ManagerProductionHostAdaptersError("manager Compose project is invalid")
    working_dir = _absolute_directory(
        compose.get("working_dir"),
        "manager Compose working directory",
    )
    raw_files = compose.get("config_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ManagerProductionHostAdaptersError(
            "manager Compose file inventory is missing"
        )
    config_files: list[Path] = []
    for record in raw_files:
        if not isinstance(record, dict):
            raise ManagerProductionHostAdaptersError(
                "manager Compose file inventory is invalid"
            )
        path = _absolute_file(record.get("path"), "manager Compose file")
        if not path.is_relative_to(working_dir) or path in config_files:
            raise ManagerProductionHostAdaptersError(
                "manager Compose file escaped or duplicated its working directory"
            )
        _verify_bound_file(path, record, "manager Compose file")
        config_files.append(path)

    environment_record = compose.get("environment")
    environment_file: Path | None = None
    if environment_record is not None:
        if not isinstance(environment_record, dict):
            raise ManagerProductionHostAdaptersError(
                "manager Compose environment binding is invalid"
            )
        environment_file = _absolute_file(
            environment_record.get("path"),
            "manager Compose environment",
        )
        if not environment_file.is_relative_to(working_dir):
            raise ManagerProductionHostAdaptersError(
                "manager Compose environment escaped its working directory"
            )
        _verify_bound_file(
            environment_file,
            environment_record,
            "manager Compose environment",
        )

    secret_root = _absolute_target(
        runtime.get("target_secret_root"),
        "manager secret root",
    )
    password_target = _absolute_target(
        runtime.get("target_password_file"),
        "manager password target",
    )
    if not password_target.is_relative_to(secret_root):
        raise ManagerProductionHostAdaptersError(
            "manager password target escaped its secret root"
        )
    if secret_root.exists() and (
        not secret_root.is_dir()
        or secret_root.is_symlink()
        or secret_root.stat().st_mode & 0o077
    ):
        raise ManagerProductionHostAdaptersError("manager secret root is unsafe")

    auth_environment_target = working_dir / _AUTH_ENV_NAME
    overlay_target = working_dir / _OVERLAY_NAME
    for target, label in (
        (password_target, "manager password target"),
        (auth_environment_target, "manager auth environment target"),
        (overlay_target, "manager Compose overlay target"),
    ):
        if target.exists() or target.is_symlink():
            raise ManagerProductionHostAdaptersError(
                f"{label} is already active before mutation"
            )

    material_environment = prep_paths["material/manager/manager.env"]
    material_password = prep_paths["material/manager/password"]
    material_overlay = prep_paths["material/manager/compose-secret-fragment.yaml"]
    material_values = _read_material_values(material_environment)
    if material_values != values:
        raise ManagerProductionHostAdaptersError(
            "manager environment material binding has drifted"
        )

    rollback_archive = execution_preparation_directory / "fresh-manager-rollback.tar.gz"
    rollback = verify_rollback_archive(rollback_archive)
    if (
        rollback.get("manager_only") is not True
        or rollback.get("restart_scope") != ["greenhouse-manager"]
        or rollback.get("forbidden_service_changes")
        != ["mosquitto", "homeassistant", "node"]
        or rollback.get("compose_project") != project
        or rollback.get("compose_working_directory") != str(working_dir)
        or rollback.get("manager_secret_root") != str(secret_root)
        or rollback.get("manager_password_target") != str(password_target)
        or rollback.get("manager_password_target_absent") is not True
    ):
        raise ManagerProductionHostAdaptersError(
            "fresh manager rollback scope or path binding is invalid"
        )
    for field in (
        "driver_contract_sha256",
        "adapter_contract_sha256",
        "runtime_binding_sha256",
        "live_binding_sha256",
        "preparation_manifest_sha256",
    ):
        if rollback.get(field) != bindings.get(field):
            raise ManagerProductionHostAdaptersError(
                f"fresh manager rollback binding failed: {field}"
            )

    binding = ManagerHostBinding(
        project=project,
        working_dir=working_dir,
        config_files=tuple(config_files),
        environment_file=environment_file,
        secret_root=secret_root,
        password_target=password_target,
        auth_environment_target=auth_environment_target,
        overlay_target=overlay_target,
        material_environment=material_environment,
        material_password=material_password,
        material_overlay=material_overlay,
        username=values["GH_MQTT_USERNAME"],
        client_id=values["GH_MQTT_CLIENT_ID"],
    )
    return binding, rollback, execution_manifest


def _extract_snapshots(
    archive_path: Path,
    rollback: Mapping[str, Any],
    workspace: Path,
    binding: ManagerHostBinding,
) -> tuple[SnapshotRecord, ...]:
    files = rollback.get("files")
    if not isinstance(files, list):
        raise ManagerProductionHostAdaptersError(
            "fresh manager rollback inventory is missing"
        )
    allowed_sources = set(binding.config_files)
    if binding.environment_file is not None:
        allowed_sources.add(binding.environment_file)
    observed_sources: set[Path] = set()
    snapshots: list[SnapshotRecord] = []
    snapshot_root = workspace / "fresh-rollback"
    snapshot_root.mkdir(mode=0o700)
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        for item in files:
            if not isinstance(item, dict):
                raise ManagerProductionHostAdaptersError(
                    "fresh manager rollback inventory is invalid"
                )
            archive_name = item.get("archive_path")
            source_name = item.get("source_path")
            if not isinstance(archive_name, str) or not isinstance(source_name, str):
                raise ManagerProductionHostAdaptersError(
                    "fresh manager rollback inventory paths are invalid"
                )
            relative = PurePosixPath(archive_name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ManagerProductionHostAdaptersError(
                    "fresh manager rollback archive path is unsafe"
                )
            source = Path(source_name).resolve()
            if source not in allowed_sources or source in observed_sources:
                raise ManagerProductionHostAdaptersError(
                    "fresh manager rollback source path is unexpected"
                )
            member = members.get(archive_name)
            if member is None or not member.isfile():
                raise ManagerProductionHostAdaptersError(
                    "fresh manager rollback archive member is missing"
                )
            stream = archive.extractfile(member)
            if stream is None:
                raise ManagerProductionHostAdaptersError(
                    "fresh manager rollback archive member cannot be read"
                )
            payload = stream.read()
            digest = item.get("sha256")
            if not isinstance(digest, str) or _sha_bytes(payload) != digest:
                raise ManagerProductionHostAdaptersError(
                    "fresh manager rollback archive member fingerprint failed"
                )
            target = snapshot_root.joinpath(*relative.parts)
            _atomic_write(
                target,
                payload,
                mode=int(item["mode"]),
                uid=int(item["uid"]),
                gid=int(item["gid"]),
                boundary=snapshot_root,
            )
            snapshots.append(
                SnapshotRecord(
                    source=source,
                    snapshot=target,
                    mode=int(item["mode"]),
                    uid=int(item["uid"]),
                    gid=int(item["gid"]),
                    sha256=digest,
                )
            )
            observed_sources.add(source)
    if observed_sources != allowed_sources:
        raise ManagerProductionHostAdaptersError(
            "fresh manager rollback source inventory is incomplete"
        )
    return tuple(snapshots)


class LiveProductionManagerDriver:
    def __init__(
        self,
        binding: ManagerHostBinding,
        *,
        probe: ManagerRuntimeProbe,
        runner: CommandRunner | None = None,
    ) -> None:
        self.binding = binding
        self.probe = probe
        self.runner = runner or SubprocessRunner()

    def _run(self, command: Sequence[str], message: str) -> str:
        code, output = self.runner.run(tuple(command))
        if code != 0:
            raise ManagerProductionHostAdaptersError(message)
        return output

    def _inspect_running_zero_restart(self) -> None:
        output = self._run(
            ("docker", "inspect", "greenhouse-manager"),
            "greenhouse-manager cannot be inspected",
        )
        try:
            documents = json.loads(output)
        except json.JSONDecodeError as error:
            raise ManagerProductionHostAdaptersError(
                "greenhouse-manager inspection returned invalid JSON"
            ) from error
        if (
            not isinstance(documents, list)
            or len(documents) != 1
            or not isinstance(documents[0], dict)
        ):
            raise ManagerProductionHostAdaptersError(
                "exactly one greenhouse-manager container is required"
            )
        document = documents[0]
        state = document.get("State")
        if (
            not isinstance(state, dict)
            or state.get("Status") != "running"
            or int(document.get("RestartCount", -1)) != 0
        ):
            raise ManagerProductionHostAdaptersError(
                "greenhouse-manager must be running with restart count zero"
            )

    def _compose_command(self, *, include_overlay: bool) -> tuple[str, ...]:
        command: list[str] = [
            "docker",
            "compose",
            "--project-directory",
            str(self.binding.working_dir),
            "--project-name",
            self.binding.project,
        ]
        for path in self.binding.config_files:
            command.extend(("-f", str(path)))
        if include_overlay:
            command.extend(("-f", str(self.binding.overlay_target)))
        command.extend(
            (
                "up",
                "-d",
                "--no-deps",
                "--force-recreate",
                "greenhouse-manager",
            )
        )
        return tuple(command)

    def recreate_manager(
        self,
        *,
        environment_file: Path,
        password_file: Path,
        overlay_file: Path,
    ) -> None:
        if (
            environment_file.resolve() != self.binding.auth_environment_target
            or password_file.resolve() != self.binding.password_target
            or overlay_file.resolve() != self.binding.overlay_target
        ):
            raise ManagerProductionHostAdaptersError(
                "manager recreate paths do not match the bound production targets"
            )
        for path, label in (
            (environment_file, "manager auth environment"),
            (password_file, "manager password"),
            (overlay_file, "manager Compose overlay"),
        ):
            _private_file(path, label)
        self._run(
            self._compose_command(include_overlay=True),
            "greenhouse-manager recreate failed",
        )
        self._inspect_running_zero_restart()

    def verify_authenticated_identity(self, username: str, client_id: str) -> None:
        self.probe.verify_authenticated_identity(username, client_id)

    def verify_ingress_subscription(self) -> None:
        self.probe.verify_ingress_subscription()

    def verify_canonical_publication(self) -> None:
        self.probe.verify_canonical_publication()

    def verify_availability_publication(self) -> None:
        self.probe.verify_availability_publication()

    def verify_discovery_publication(self) -> None:
        self.probe.verify_discovery_publication()

    def verify_reconnect(self) -> None:
        self.probe.verify_reconnect()

    def verify_existing_entities(self) -> None:
        self.probe.verify_existing_entities()

    def postactivation_audit(self) -> dict[str, object]:
        return self.probe.postactivation_audit()

    def recreate_after_rollback(self) -> None:
        self._run(
            self._compose_command(include_overlay=False),
            "greenhouse-manager rollback recreate failed",
        )
        self._inspect_running_zero_restart()

    def verify_legacy_anonymous_path(self) -> None:
        self.probe.verify_legacy_anonymous_path()


class ManagerProductionHostTransactionAdapters:
    def __init__(
        self,
        driver_contract_file: str | Path,
        execution_preparation_directory: str | Path,
        preparation_directory: str | Path,
        workspace_directory: str | Path,
        *,
        driver: ManagerProductionDriver,
        now: datetime | None = None,
    ) -> None:
        self.driver_contract_file = Path(driver_contract_file).expanduser().resolve()
        self.execution_preparation = Path(
            execution_preparation_directory
        ).expanduser().resolve()
        self.preparation = Path(preparation_directory).expanduser().resolve()
        self.workspace = Path(workspace_directory).expanduser().resolve()
        self.driver = driver
        self.now = now
        self.binding: ManagerHostBinding | None = None
        self.rollback: dict[str, Any] | None = None
        self.snapshots: tuple[SnapshotRecord, ...] | None = None
        self.prepared = False
        self.mutation_started = False

    def prepare(self) -> dict[str, object]:
        if self.prepared:
            return self.installation_report()
        _private_directory(self.workspace, "manager production transaction workspace")
        if any(self.workspace.iterdir()):
            raise ManagerProductionHostAdaptersError(
                "manager production transaction workspace is not empty"
            )
        binding, rollback, _manifest = _load_binding(
            self.driver_contract_file,
            self.execution_preparation,
            self.preparation,
            now=self.now,
        )
        archive = self.execution_preparation / "fresh-manager-rollback.tar.gz"
        snapshots = _extract_snapshots(archive, rollback, self.workspace, binding)
        inventory = {
            "schema": SNAPSHOT_SCHEMA,
            "record_count": len(snapshots),
            "records": [
                {
                    "source_fingerprint": _sha_bytes(str(item.source).encode("utf-8"))[:16],
                    "sha256": item.sha256,
                    "mode": item.mode,
                }
                for item in snapshots
            ],
            "path_values_redacted": True,
            "secret_values_included": False,
        }
        workspace_stat = self.workspace.stat()
        _atomic_write(
            self.workspace / "snapshot-inventory.json",
            (_canonical_json(inventory) + "\n").encode("utf-8"),
            mode=0o600,
            uid=workspace_stat.st_uid,
            gid=workspace_stat.st_gid,
            boundary=self.workspace,
        )
        self.binding = binding
        self.rollback = rollback
        self.snapshots = snapshots
        self.prepared = True
        return self.installation_report()

    def installation_report(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "production_transaction_adapters_installed": self.prepared,
            "production_manager_driver_installed": self.prepared,
            "execution_entrypoint_installed": False,
            "greenhouse_manager_only": True,
            "mosquitto_target_allowed": False,
            "homeassistant_target_allowed": False,
            "node_target_allowed": False,
            "snapshot_complete": self.prepared,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "path_values_redacted": True,
            "secret_values_included": False,
        }

    def mutation_executor(self) -> dict[str, object]:
        self.prepare()
        if self.binding is None:
            raise ManagerProductionHostAdaptersError(
                "manager production host binding is unavailable"
            )
        binding = self.binding
        self.mutation_started = True
        password_stat = binding.material_password.stat()
        environment_stat = binding.material_environment.stat()
        overlay_stat = binding.material_overlay.stat()
        _atomic_write(
            binding.password_target,
            binding.material_password.read_bytes(),
            mode=0o600,
            uid=password_stat.st_uid,
            gid=password_stat.st_gid,
            boundary=binding.secret_root,
        )
        _atomic_write(
            binding.auth_environment_target,
            binding.material_environment.read_bytes(),
            mode=0o600,
            uid=environment_stat.st_uid,
            gid=environment_stat.st_gid,
            boundary=binding.working_dir,
        )
        _atomic_write(
            binding.overlay_target,
            binding.material_overlay.read_bytes(),
            mode=0o600,
            uid=overlay_stat.st_uid,
            gid=overlay_stat.st_gid,
            boundary=binding.working_dir,
        )
        self.driver.recreate_manager(
            environment_file=binding.auth_environment_target,
            password_file=binding.password_target,
            overlay_file=binding.overlay_target,
        )
        self.driver.verify_authenticated_identity(binding.username, binding.client_id)
        self.driver.verify_ingress_subscription()
        self.driver.verify_canonical_publication()
        self.driver.verify_availability_publication()
        self.driver.verify_discovery_publication()
        self.driver.verify_reconnect()
        self.driver.verify_existing_entities()
        return {
            "schema": SCHEMA,
            "mutation_started": True,
            "manager_material_installed": True,
            "greenhouse_manager_recreated": True,
            "manager_restart_count_zero": True,
            "authenticated_identity_verified": True,
            "ingress_subscription_verified": True,
            "canonical_publication_verified": True,
            "availability_publication_verified": True,
            "discovery_publication_verified": True,
            "reconnect_verified": True,
            "existing_entities_verified": True,
            "mosquitto_modified": False,
            "homeassistant_modified": False,
            "nodes_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "current_services_modified": True,
        }

    def postactivation_auditor(self) -> dict[str, object]:
        report = self.driver.postactivation_audit()
        required = {
            "manager_identity_migrated": True,
            "manager_authenticated": True,
            "ingress_subscription_verified": True,
            "canonical_publication_verified": True,
            "availability_publication_verified": True,
            "discovery_publication_verified": True,
            "reconnect_verified": True,
            "existing_entities_verified": True,
            "rollback_required": False,
            "node_credentials_delivered": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }
        for field, expected in required.items():
            if report.get(field) is not expected:
                raise ManagerProductionHostAdaptersError(
                    f"manager production postactivation audit failed: {field}"
                )
        checks = report.get("checks")
        if not isinstance(checks, dict) or not checks or any(
            value is not True for value in checks.values()
        ):
            raise ManagerProductionHostAdaptersError(
                "manager production postactivation checks are not all passing"
            )
        return report

    def rollback_executor(self) -> dict[str, object]:
        self.prepare()
        if self.binding is None or self.snapshots is None:
            raise ManagerProductionHostAdaptersError(
                "manager production rollback snapshot is unavailable"
            )
        binding = self.binding
        for record in self.snapshots:
            _atomic_write(
                record.source,
                record.snapshot.read_bytes(),
                mode=record.mode,
                uid=record.uid,
                gid=record.gid,
                boundary=binding.working_dir,
            )
        _unlink(binding.overlay_target, boundary=binding.working_dir)
        _unlink(binding.auth_environment_target, boundary=binding.working_dir)
        _unlink(binding.password_target, boundary=binding.secret_root)
        self.driver.recreate_after_rollback()
        self.driver.verify_legacy_anonymous_path()
        self.driver.verify_existing_entities()
        for record in self.snapshots:
            if (
                not record.source.is_file()
                or record.source.is_symlink()
                or record.source.stat().st_mode & 0o777 != record.mode
                or _sha_path(record.source) != record.sha256
            ):
                raise ManagerProductionHostAdaptersError(
                    "manager production rollback inventory does not match baseline"
                )
        if any(
            path.exists() or path.is_symlink()
            for path in (
                binding.overlay_target,
                binding.auth_environment_target,
                binding.password_target,
            )
        ):
            raise ManagerProductionHostAdaptersError(
                "manager authentication mutation state remains after rollback"
            )
        return {
            "schema": SCHEMA,
            "rollback_completed": True,
            "manager_material_restored": True,
            "compose_binding_restored": True,
            "greenhouse_manager_recreated": True,
            "legacy_anonymous_path_verified": True,
            "existing_entities_verified": True,
            "mosquitto_modified": False,
            "homeassistant_modified": False,
            "nodes_modified": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }
