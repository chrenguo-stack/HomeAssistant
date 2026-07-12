from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from .t1_broker_identity_activation_readiness_transaction_plan import (
    verify_activation_readiness_transaction_plan,
)
from .t1_broker_identity_production_executor_contract import (
    verify_production_executor_contract,
)
from .t1_broker_identity_production_transaction_adapter_contract import (
    verify_production_transaction_adapter_contract,
)
from .t1_broker_identity_runtime_binding_manifest import (
    verify_runtime_binding_manifest,
)
from .t1_shadow import PLUGIN_CONFIG_LINE, PLUGIN_LINE, PLUGIN_PASSWORD_INIT_LINE

SCHEMA = "gh.m2.t1-broker-identity-production-transaction-adapters/1"
_REQUIRED_MATERIAL = (
    "material/broker/dynsec-request.json",
    "material/broker/mosquitto-plugin.conf",
    "material/bootstrap/dynsec-password-init",
    "material/bootstrap/admin-client.conf",
    "material/provisioning/mosquitto-client.conf",
    "material/homeassistant/mqtt-update.json",
)

DocumentVerifier = Callable[[dict[str, object]], dict[str, object]]
ManifestVerifier = Callable[[str | Path], dict[str, object]]


class BrokerIdentityProductionTransactionAdaptersError(RuntimeError):
    pass


class ProductionBrokerDriver(Protocol):
    def restart_mosquitto(self) -> None: ...

    def wait_for_dynamic_security_state(self, state_file: Path) -> None: ...

    def apply_exact_request(
        self,
        commands: Sequence[dict[str, Any]],
        bootstrap_config: str,
    ) -> None: ...

    def verify_provisioning_identity(self, provisioning_config: str) -> None: ...

    def delete_bootstrap_admin(self, provisioning_config: str) -> None: ...

    def verify_bootstrap_rejected(self, bootstrap_config: str) -> None: ...

    def postactivation_audit(
        self,
        *,
        expected_retained_topic: str,
        homeassistant_update: Mapping[str, Any],
        provisioning_config: str,
        bootstrap_config: str,
    ) -> dict[str, object]: ...

    def restart_after_rollback(self) -> None: ...

    def verify_anonymous_retained_state(self, topic: str) -> None: ...


@dataclass(frozen=True)
class RuntimePaths:
    config_source: Path
    data_source: Path
    config_file: Path
    dynamic_security_state_file: Path


@dataclass(frozen=True)
class PathRecord:
    kind: str
    mode: int
    uid: int
    gid: int
    sha256: str | None


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
        raise BrokerIdentityProductionTransactionAdaptersError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityProductionTransactionAdaptersError(
            f"{label} is invalid"
        ) from error
    if not isinstance(document, dict):
        raise BrokerIdentityProductionTransactionAdaptersError(
            f"{label} must be a JSON object"
        )
    return document


def _private_file(path: Path, label: str) -> None:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityProductionTransactionAdaptersError(
            f"{label} is missing, unsafe, or not mode 0600"
        )


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise BrokerIdentityProductionTransactionAdaptersError(
            f"{label} path is missing"
        )
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise BrokerIdentityProductionTransactionAdaptersError(
            f"{label} path is unsafe"
        )
    return relative


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(
    path: Path,
    data: bytes,
    *,
    mode: int,
    uid: int,
    gid: int,
) -> None:
    if path.exists() and path.is_symlink():
        raise BrokerIdentityProductionTransactionAdaptersError(
            "atomic write target cannot be a symlink"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, mode)
        os.chown(temporary_path, uid, gid)
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _unlink_and_fsync(path: Path) -> None:
    if path.is_symlink():
        raise BrokerIdentityProductionTransactionAdaptersError(
            "unlink target cannot be a symlink"
        )
    path.unlink(missing_ok=True)
    _fsync_directory(path.parent)


def _active_lines(path: Path) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _request_commands(path: Path) -> tuple[dict[str, Any], ...]:
    request = _read_private_json(path, "Dynamic Security request")
    raw = request.get("commands")
    if not isinstance(raw, list) or not raw:
        raise BrokerIdentityProductionTransactionAdaptersError(
            "Dynamic Security request is empty"
        )
    result: list[dict[str, Any]] = []
    for command in raw:
        if not isinstance(command, dict) or not isinstance(
            command.get("command"), str
        ):
            raise BrokerIdentityProductionTransactionAdaptersError(
                "Dynamic Security request is invalid"
            )
        result.append(command)
    return tuple(result)


def _record_tree(root: Path) -> dict[str, PathRecord]:
    if not root.is_dir() or root.is_symlink():
        raise BrokerIdentityProductionTransactionAdaptersError(
            "snapshot source directory is unsafe"
        )
    records: dict[str, PathRecord] = {}
    root_stat = root.stat()
    records["."] = PathRecord(
        kind="directory",
        mode=root_stat.st_mode & 0o777,
        uid=root_stat.st_uid,
        gid=root_stat.st_gid,
        sha256=None,
    )
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BrokerIdentityProductionTransactionAdaptersError(
                "snapshot source contains a symlink"
            )
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        if path.is_dir():
            records[relative] = PathRecord(
                kind="directory",
                mode=stat.st_mode & 0o777,
                uid=stat.st_uid,
                gid=stat.st_gid,
                sha256=None,
            )
        elif path.is_file():
            records[relative] = PathRecord(
                kind="file",
                mode=stat.st_mode & 0o777,
                uid=stat.st_uid,
                gid=stat.st_gid,
                sha256=_sha256_path(path),
            )
        else:
            raise BrokerIdentityProductionTransactionAdaptersError(
                "snapshot source contains an unsupported entry"
            )
    return records


def _copy_snapshot(source: Path, destination: Path) -> dict[str, PathRecord]:
    records = _record_tree(source)
    shutil.copytree(source, destination, copy_function=shutil.copy2)
    return records


def _inventory_document(records: Mapping[str, PathRecord]) -> dict[str, object]:
    return {
        relative: {
            "kind": record.kind,
            "mode": record.mode,
            "uid": record.uid,
            "gid": record.gid,
            "sha256": record.sha256,
        }
        for relative, record in sorted(records.items())
    }


def _restore_tree(
    snapshot: Path,
    target: Path,
    records: Mapping[str, PathRecord],
) -> None:
    current = _record_tree(target)
    for relative, record in sorted(
        current.items(),
        key=lambda item: len(PurePosixPath(item[0]).parts),
        reverse=True,
    ):
        if relative == "." or relative in records:
            continue
        path = target.joinpath(*PurePosixPath(relative).parts)
        if record.kind == "file":
            _unlink_and_fsync(path)
        else:
            path.rmdir()
            _fsync_directory(path.parent)

    directories = [
        (relative, record)
        for relative, record in records.items()
        if record.kind == "directory"
    ]
    directories.sort(key=lambda item: len(PurePosixPath(item[0]).parts))
    for relative, record in directories:
        path = target if relative == "." else target.joinpath(
            *PurePosixPath(relative).parts
        )
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, record.mode)
        os.chown(path, record.uid, record.gid)

    files = [
        (relative, record)
        for relative, record in records.items()
        if record.kind == "file"
    ]
    for relative, record in sorted(files):
        source = snapshot.joinpath(*PurePosixPath(relative).parts)
        destination = target.joinpath(*PurePosixPath(relative).parts)
        data = source.read_bytes()
        if record.sha256 != _sha256_bytes(data):
            raise BrokerIdentityProductionTransactionAdaptersError(
                "snapshot file fingerprint has drifted"
            )
        _atomic_write(
            destination,
            data,
            mode=record.mode,
            uid=record.uid,
            gid=record.gid,
        )

    if _record_tree(target) != dict(records):
        raise BrokerIdentityProductionTransactionAdaptersError(
            "restored tree does not match the transaction snapshot"
        )


def _runtime_paths(manifest: Mapping[str, Any]) -> RuntimePaths:
    values = manifest.get("paths")
    if not isinstance(values, dict):
        raise BrokerIdentityProductionTransactionAdaptersError(
            "runtime path binding is missing"
        )

    def bound_path(name: str, *, directory: bool) -> Path:
        raw = values.get(name)
        if not isinstance(raw, str):
            raise BrokerIdentityProductionTransactionAdaptersError(
                f"runtime path binding is missing: {name}"
            )
        path = Path(raw).expanduser()
        if not path.is_absolute() or path.is_symlink():
            raise BrokerIdentityProductionTransactionAdaptersError(
                f"runtime path binding is unsafe: {name}"
            )
        resolved = path.resolve()
        if directory and not resolved.is_dir():
            raise BrokerIdentityProductionTransactionAdaptersError(
                f"runtime directory is missing: {name}"
            )
        if not directory and not resolved.is_file():
            raise BrokerIdentityProductionTransactionAdaptersError(
                f"runtime file is missing: {name}"
            )
        return resolved

    config_source = bound_path("config_source", directory=True)
    data_source = bound_path("data_source", directory=True)
    config_file = bound_path("config_file", directory=False)
    raw_state = values.get("dynamic_security_state_file")
    if not isinstance(raw_state, str):
        raise BrokerIdentityProductionTransactionAdaptersError(
            "Dynamic Security state path binding is missing"
        )
    state = Path(raw_state).expanduser()
    if not state.is_absolute() or state.is_symlink():
        raise BrokerIdentityProductionTransactionAdaptersError(
            "Dynamic Security state path binding is unsafe"
        )
    state = state.resolve(strict=False)
    if not config_file.is_relative_to(config_source):
        raise BrokerIdentityProductionTransactionAdaptersError(
            "Broker configuration escaped the bound config source"
        )
    if not state.is_relative_to(data_source):
        raise BrokerIdentityProductionTransactionAdaptersError(
            "Dynamic Security state escaped the bound data source"
        )
    return RuntimePaths(
        config_source=config_source,
        data_source=data_source,
        config_file=config_file,
        dynamic_security_state_file=state,
    )


class ProductionTransactionAdapters:
    def __init__(
        self,
        adapter_contract_file: str | Path,
        transaction_plan_file: str | Path,
        executor_contract_file: str | Path,
        runtime_binding_manifest_file: str | Path,
        handoff_directory: str | Path,
        workspace_directory: str | Path,
        *,
        expected_retained_topic: str,
        driver: ProductionBrokerDriver,
        adapter_contract_verifier: DocumentVerifier = (
            verify_production_transaction_adapter_contract
        ),
        plan_verifier: DocumentVerifier = verify_activation_readiness_transaction_plan,
        executor_verifier: DocumentVerifier = verify_production_executor_contract,
        manifest_verifier: ManifestVerifier = verify_runtime_binding_manifest,
    ) -> None:
        if not expected_retained_topic.startswith("gh/"):
            raise ValueError("expected retained topic must be in the gh namespace")
        self.adapter_contract_file = Path(adapter_contract_file).expanduser().resolve()
        self.transaction_plan_file = Path(transaction_plan_file).expanduser().resolve()
        self.executor_contract_file = Path(executor_contract_file).expanduser().resolve()
        self.runtime_manifest_file = Path(
            runtime_binding_manifest_file
        ).expanduser().resolve()
        self.handoff = Path(handoff_directory).expanduser().resolve()
        self.workspace = Path(workspace_directory).expanduser().resolve()
        self.expected_retained_topic = expected_retained_topic
        self.driver = driver
        self.adapter_contract_verifier = adapter_contract_verifier
        self.plan_verifier = plan_verifier
        self.executor_verifier = executor_verifier
        self.manifest_verifier = manifest_verifier
        self.paths: RuntimePaths | None = None
        self.config_snapshot: Path | None = None
        self.data_snapshot: Path | None = None
        self.config_inventory: dict[str, PathRecord] | None = None
        self.data_inventory: dict[str, PathRecord] | None = None
        self.mutation_started = False
        self.prepared = False

    def _validate_bindings(self) -> tuple[dict[str, Any], dict[str, Any]]:
        adapter = _read_private_json(
            self.adapter_contract_file,
            "production transaction adapter contract",
        )
        plan = _read_private_json(self.transaction_plan_file, "transaction plan")
        executor = _read_private_json(
            self.executor_contract_file,
            "production executor contract",
        )
        manifest = _read_private_json(
            self.runtime_manifest_file,
            "runtime binding manifest",
        )
        adapter_result = self.adapter_contract_verifier(adapter)
        plan_result = self.plan_verifier(plan)
        executor_result = self.executor_verifier(executor)
        manifest_result = self.manifest_verifier(self.runtime_manifest_file)
        for label, result in (
            ("adapter contract", adapter_result),
            ("transaction plan", plan_result),
            ("executor contract", executor_result),
            ("runtime manifest", manifest_result),
        ):
            if result.get("verified") is not True:
                raise BrokerIdentityProductionTransactionAdaptersError(
                    f"{label} verification is incomplete"
                )
        required_pairs = (
            (adapter.get("transaction_plan_sha256"), plan.get("plan_sha256")),
            (adapter.get("contract_sha256"), executor.get("contract_sha256")),
            (
                adapter.get("runtime_binding_manifest_sha256"),
                manifest.get("manifest_sha256"),
            ),
        )
        if any(left != right for left, right in required_pairs):
            raise BrokerIdentityProductionTransactionAdaptersError(
                "production adapter input binding does not match"
            )
        return executor, manifest

    def _validate_handoff(self, executor: Mapping[str, Any]) -> None:
        if not self.handoff.is_dir() or self.handoff.is_symlink():
            raise BrokerIdentityProductionTransactionAdaptersError(
                "activation handoff directory is unsafe"
            )
        if executor.get("handoff") != self.handoff.name:
            raise BrokerIdentityProductionTransactionAdaptersError(
                "activation handoff name is not bound to the executor contract"
            )
        bindings = executor.get("material_bindings")
        if not isinstance(bindings, list):
            raise BrokerIdentityProductionTransactionAdaptersError(
                "executor material binding inventory is missing"
            )
        observed: dict[str, tuple[str, bool]] = {}
        for item in bindings:
            if not isinstance(item, dict):
                raise BrokerIdentityProductionTransactionAdaptersError(
                    "executor material binding inventory is invalid"
                )
            relative = _safe_relative(item.get("path"), "executor material")
            path = self.handoff.joinpath(*relative.parts)
            _private_file(path, f"activation handoff material {relative}")
            expected_sha = item.get("sha256")
            if not isinstance(expected_sha, str) or _sha256_path(path) != expected_sha:
                raise BrokerIdentityProductionTransactionAdaptersError(
                    f"activation handoff material drifted: {relative}"
                )
            observed[relative.as_posix()] = (
                expected_sha,
                item.get("contains_secret") is True,
            )
        if set(observed) != set(_REQUIRED_MATERIAL):
            raise BrokerIdentityProductionTransactionAdaptersError(
                "activation handoff material inventory is incomplete"
            )

    def prepare(self) -> dict[str, object]:
        if self.prepared:
            return self.installation_report()
        executor, manifest = self._validate_bindings()
        self._validate_handoff(executor)
        self.paths = _runtime_paths(manifest)
        baseline_sha = manifest.get("baseline_config_sha256")
        if baseline_sha != _sha256_path(self.paths.config_file):
            raise BrokerIdentityProductionTransactionAdaptersError(
                "live Broker baseline configuration has drifted"
            )
        if self.paths.dynamic_security_state_file.exists():
            raise BrokerIdentityProductionTransactionAdaptersError(
                "Dynamic Security state already exists before mutation"
            )
        if self.workspace.exists() and self.workspace.is_symlink():
            raise BrokerIdentityProductionTransactionAdaptersError(
                "production transaction workspace is unsafe"
            )
        self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.workspace.stat().st_mode & 0o077:
            raise BrokerIdentityProductionTransactionAdaptersError(
                "production transaction workspace must be private"
            )
        self.config_snapshot = self.workspace / "snapshot-config"
        self.data_snapshot = self.workspace / "snapshot-data"
        if self.config_snapshot.exists() or self.data_snapshot.exists():
            raise BrokerIdentityProductionTransactionAdaptersError(
                "production transaction snapshot already exists"
            )
        self.config_inventory = _copy_snapshot(
            self.paths.config_source,
            self.config_snapshot,
        )
        self.data_inventory = _copy_snapshot(
            self.paths.data_source,
            self.data_snapshot,
        )
        inventory = {
            "schema": "gh.m2.t1-broker-identity-production-snapshot-inventory/1",
            "config": _inventory_document(self.config_inventory),
            "data": _inventory_document(self.data_inventory),
        }
        inventory_path = self.workspace / "snapshot-inventory.json"
        workspace_stat = self.workspace.stat()
        _atomic_write(
            inventory_path,
            (_canonical_json(inventory) + "\n").encode("utf-8"),
            mode=0o600,
            uid=workspace_stat.st_uid,
            gid=workspace_stat.st_gid,
        )
        self.prepared = True
        return self.installation_report()

    def installation_report(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "production_transaction_adapters_installed": self.prepared,
            "live_driver_injected": True,
            "execution_entrypoint_installed": False,
            "authorization_claimed": False,
            "claim_enabled": False,
            "production_executor_available": False,
            "execution_enabled": False,
            "apply_enabled": False,
            "ready_for_live_activation": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "snapshot_complete": self.prepared,
            "path_values_redacted": True,
            "secret_values_included": False,
        }

    def mutation_executor(self) -> dict[str, object]:
        self.prepare()
        if (
            self.paths is None
            or self.config_inventory is None
            or self.data_inventory is None
        ):
            raise BrokerIdentityProductionTransactionAdaptersError(
                "production transaction adapters are not prepared"
            )
        plugin_path = self.handoff / "material/broker/mosquitto-plugin.conf"
        plugin_lines = _active_lines(plugin_path)
        canonical = (PLUGIN_LINE, PLUGIN_CONFIG_LINE, PLUGIN_PASSWORD_INIT_LINE)
        if plugin_lines != canonical:
            raise BrokerIdentityProductionTransactionAdaptersError(
                "activation handoff plugin configuration is not canonical"
            )
        original = self.paths.config_file.read_text(encoding="utf-8")
        active = tuple(
            line.strip()
            for line in original.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        if any(line in active for line in canonical):
            raise BrokerIdentityProductionTransactionAdaptersError(
                "live Broker configuration is already mutated"
            )
        config_stat = self.paths.config_file.stat()
        mutated = original.rstrip("\n") + "\n" + "\n".join(canonical) + "\n"
        self.mutation_started = True
        _atomic_write(
            self.paths.config_file,
            mutated.encode("utf-8"),
            mode=config_stat.st_mode & 0o777,
            uid=config_stat.st_uid,
            gid=config_stat.st_gid,
        )
        config_dir_stat = self.paths.config_source.stat()
        password_init = self.paths.config_source / "dynsec-password-init"
        _atomic_write(
            password_init,
            (self.handoff / "material/bootstrap/dynsec-password-init").read_bytes(),
            mode=0o600,
            uid=config_dir_stat.st_uid,
            gid=config_dir_stat.st_gid,
        )
        self.driver.restart_mosquitto()
        self.driver.wait_for_dynamic_security_state(
            self.paths.dynamic_security_state_file
        )
        if not self.paths.dynamic_security_state_file.is_file():
            raise BrokerIdentityProductionTransactionAdaptersError(
                "Dynamic Security state was not created"
            )
        data_stat = self.paths.data_source.stat()
        os.chmod(self.paths.dynamic_security_state_file, 0o600)
        os.chown(
            self.paths.dynamic_security_state_file,
            data_stat.st_uid,
            data_stat.st_gid,
        )
        _unlink_and_fsync(password_init)

        bootstrap = (
            self.handoff / "material/bootstrap/admin-client.conf"
        ).read_text(encoding="utf-8")
        provisioning = (
            self.handoff / "material/provisioning/mosquitto-client.conf"
        ).read_text(encoding="utf-8")
        commands = _request_commands(
            self.handoff / "material/broker/dynsec-request.json"
        )
        self.driver.apply_exact_request(commands, bootstrap)
        self.driver.verify_provisioning_identity(provisioning)
        self.driver.delete_bootstrap_admin(provisioning)
        self.driver.verify_bootstrap_rejected(bootstrap)
        self.driver.verify_provisioning_identity(provisioning)
        return {
            "mutation_started": True,
            "mosquitto_restarted": True,
            "bootstrap_admin_removed": True,
            "provisioning_identity_verified": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "current_services_modified": True,
        }

    def postactivation_auditor(self) -> dict[str, object]:
        update = _read_private_json(
            self.handoff / "material/homeassistant/mqtt-update.json",
            "Home Assistant MQTT update material",
        )
        provisioning = (
            self.handoff / "material/provisioning/mosquitto-client.conf"
        ).read_text(encoding="utf-8")
        bootstrap = (
            self.handoff / "material/bootstrap/admin-client.conf"
        ).read_text(encoding="utf-8")
        report = self.driver.postactivation_audit(
            expected_retained_topic=self.expected_retained_topic,
            homeassistant_update=update,
            provisioning_config=provisioning,
            bootstrap_config=bootstrap,
        )
        required = {
            "activation_verified": True,
            "rollback_required": False,
            "broker_identity_activated": True,
            "ready_for_homeassistant_reconfigure_handoff": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }
        for field, expected in required.items():
            if report.get(field) is not expected:
                raise BrokerIdentityProductionTransactionAdaptersError(
                    f"production postactivation audit failed: {field}"
                )
        checks = report.get("checks")
        if (
            not isinstance(checks, dict)
            or not checks
            or any(value is not True for value in checks.values())
        ):
            raise BrokerIdentityProductionTransactionAdaptersError(
                "production postactivation checks are not all passing"
            )
        return report

    def rollback_executor(self) -> dict[str, object]:
        if (
            not self.prepared
            or self.paths is None
            or self.config_snapshot is None
            or self.data_snapshot is None
            or self.config_inventory is None
            or self.data_inventory is None
        ):
            raise BrokerIdentityProductionTransactionAdaptersError(
                "production rollback snapshot is unavailable"
            )
        _restore_tree(
            self.config_snapshot,
            self.paths.config_source,
            self.config_inventory,
        )
        _restore_tree(
            self.data_snapshot,
            self.paths.data_source,
            self.data_inventory,
        )
        self.driver.restart_after_rollback()
        self.driver.verify_anonymous_retained_state(self.expected_retained_topic)
        if self.paths.dynamic_security_state_file.exists():
            raise BrokerIdentityProductionTransactionAdaptersError(
                "Dynamic Security state remained after rollback"
            )
        return {
            "rollback_completed": True,
            "baseline_config_restored": True,
            "complete_snapshot_inventory_restored": True,
            "dynamic_security_state_absent": True,
            "anonymous_retained_state_readable": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "current_services_modified": False,
        }
