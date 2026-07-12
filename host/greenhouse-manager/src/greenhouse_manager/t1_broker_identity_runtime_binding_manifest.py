from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .t1_broker_identity_activation_checks import Runner
from .t1_broker_identity_production_driver_contract import (
    BrokerIdentityProductionDriverContractError,
    verify_production_driver_contract,
)
from .t1_broker_identity_production_executor_contract import (
    BrokerIdentityProductionExecutorContractError,
    verify_production_executor_contract,
)
from .t1_shadow import SubprocessRunner

SCHEMA = "gh.m2.t1-broker-identity-runtime-binding-manifest/1"
SUMMARY_SCHEMA = "gh.m2.t1-broker-identity-runtime-binding-capture/1"
LIVE_MOUNT_GATE_SCHEMA = "gh.m2.t1-broker-identity-live-mount-gate/1"
DriverVerifier = Callable[[dict[str, object]], dict[str, object]]
ExecutorVerifier = Callable[[dict[str, object]], dict[str, object]]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OUTPUT_PREFIX = "greenhouse-m2-runtime-bindings"


class BrokerIdentityRuntimeBindingManifestError(RuntimeError):
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


def _sha256_document(document: dict[str, object]) -> str:
    return _sha256_text(_canonical_json(document))


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise BrokerIdentityRuntimeBindingManifestError(
            f"{label} fingerprint is invalid"
        )
    return value


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityRuntimeBindingManifestError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityRuntimeBindingManifestError(
            f"{label} is invalid"
        ) from error
    if not isinstance(document, dict):
        raise BrokerIdentityRuntimeBindingManifestError(
            f"{label} must be a JSON object"
        )
    return document


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_private_write(path: Path, value: str) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _private_output_directory(path: Path) -> Path:
    if not path.name.startswith(_OUTPUT_PREFIX):
        raise BrokerIdentityRuntimeBindingManifestError(
            "runtime binding output directory name is not allowed"
        )
    if path.exists() and path.is_symlink():
        raise BrokerIdentityRuntimeBindingManifestError(
            "runtime binding output directory is unsafe"
        )
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = path.resolve()
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise BrokerIdentityRuntimeBindingManifestError(
            "runtime binding output directory must be private"
        )
    return path


def _require_success(runner: Runner, command: Sequence[str], message: str) -> str:
    code, output = runner.run(tuple(command))
    if code != 0:
        raise BrokerIdentityRuntimeBindingManifestError(message)
    return output


def _inspect_mosquitto(runner: Runner) -> dict[str, Any]:
    output = _require_success(
        runner,
        ("docker", "inspect", "mosquitto"),
        "live Mosquitto container cannot be inspected",
    )
    try:
        values = json.loads(output)
    except json.JSONDecodeError as error:
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto inspect returned invalid JSON"
        ) from error
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto inspect returned an unexpected document"
        )
    return values[0]


def _single_bind_mount(document: dict[str, Any], destination: str) -> Path:
    mounts = document.get("Mounts")
    if not isinstance(mounts, list):
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto mount inventory is missing"
        )
    matches = [
        item
        for item in mounts
        if isinstance(item, dict) and item.get("Destination") == destination
    ]
    if len(matches) != 1:
        raise BrokerIdentityRuntimeBindingManifestError(
            f"live Mosquitto must have one {destination} mount"
        )
    mount = matches[0]
    if mount.get("Type") != "bind" or mount.get("RW") is not True:
        raise BrokerIdentityRuntimeBindingManifestError(
            f"live Mosquitto {destination} mount must be a writable bind mount"
        )
    source = mount.get("Source")
    if not isinstance(source, str) or not source:
        raise BrokerIdentityRuntimeBindingManifestError(
            f"live Mosquitto {destination} source is missing"
        )
    path = Path(source).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise BrokerIdentityRuntimeBindingManifestError(
            f"live Mosquitto {destination} source is unsafe"
        )
    path = path.resolve()
    if not path.is_dir():
        raise BrokerIdentityRuntimeBindingManifestError(
            f"live Mosquitto {destination} source is unsafe"
        )
    return path


def _compose_binding(document: dict[str, Any]) -> tuple[Path, tuple[Path, ...]]:
    config = document.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if not isinstance(labels, dict):
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto Compose labels are missing"
        )
    raw_working = labels.get("com.docker.compose.project.working_dir")
    raw_files = labels.get("com.docker.compose.project.config_files")
    if not isinstance(raw_working, str) or not raw_working.strip():
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto Compose working directory is missing"
        )
    if not isinstance(raw_files, str) or not raw_files.strip():
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto Compose config files are missing"
        )
    working_path = Path(raw_working).expanduser()
    if not working_path.is_absolute() or working_path.is_symlink():
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto Compose working directory is unsafe"
        )
    working = working_path.resolve()
    if not working.is_dir():
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto Compose working directory is unsafe"
        )
    files: list[Path] = []
    for raw in raw_files.split(","):
        value = raw.strip()
        if not value:
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = working / path
        if path.is_symlink():
            raise BrokerIdentityRuntimeBindingManifestError(
                "live Mosquitto Compose config file is unsafe"
            )
        path = path.resolve()
        if not path.is_file() or not path.is_relative_to(working):
            raise BrokerIdentityRuntimeBindingManifestError(
                "live Mosquitto Compose config file is unsafe"
            )
        files.append(path)
    if not files:
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto Compose config file binding is empty"
        )
    return working, tuple(files)


def _runtime_identity(document: dict[str, Any]) -> dict[str, object]:
    state = document.get("State")
    config = document.get("Config")
    container_id = document.get("Id")
    image_id = document.get("Image")
    image_ref = config.get("Image") if isinstance(config, dict) else None
    if not isinstance(state, dict) or state.get("Status") != "running":
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto is not running"
        )
    restart_count = document.get("RestartCount")
    if restart_count != 0:
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto restart count is not zero"
        )
    started_at = state.get("StartedAt")
    if not all(
        isinstance(value, str) and value
        for value in (container_id, image_id, image_ref, started_at)
    ):
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto runtime identity is incomplete"
        )
    return {
        "container_name": "mosquitto",
        "container_id": container_id,
        "image_id": image_id,
        "image_ref": image_ref,
        "started_at": started_at,
        "restart_count": 0,
    }


def _path_identity(path: Path, *, include_sha256: bool = False) -> dict[str, object]:
    stat = path.stat()
    identity: dict[str, object] = {
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "mode": stat.st_mode & 0o777,
        "uid": stat.st_uid,
        "gid": stat.st_gid,
    }
    if include_sha256:
        identity["sha256"] = _sha256_path(path)
    return identity


def _validate_inputs(
    driver: dict[str, object],
    executor: dict[str, object],
    gate: dict[str, object],
    *,
    driver_verifier: DriverVerifier,
    executor_verifier: ExecutorVerifier,
) -> tuple[str, str, str, str]:
    driver_result = driver_verifier(driver)
    executor_result = executor_verifier(executor)
    if driver_result.get("verified") is not True:
        raise BrokerIdentityRuntimeBindingManifestError(
            "production driver contract verification is incomplete"
        )
    if executor_result.get("verified") is not True:
        raise BrokerIdentityRuntimeBindingManifestError(
            "production executor contract verification is incomplete"
        )
    driver_sha = _require_sha256(
        driver_result.get("driver_contract_sha256"),
        "production driver contract",
    )
    contract_sha = _require_sha256(
        executor_result.get("contract_sha256"),
        "production executor contract",
    )
    mount_sha = _require_sha256(
        driver.get("mount_binding_sha256"),
        "production driver mount binding",
    )
    skeleton_sha = _require_sha256(
        driver.get("skeleton_sha256"),
        "production driver skeleton",
    )
    if driver.get("contract_sha256") != contract_sha:
        raise BrokerIdentityRuntimeBindingManifestError(
            "production driver executor binding does not match"
        )
    if gate.get("schema") != LIVE_MOUNT_GATE_SCHEMA:
        raise BrokerIdentityRuntimeBindingManifestError(
            "live mount gate schema is invalid"
        )
    if gate.get("contract_sha256") != contract_sha:
        raise BrokerIdentityRuntimeBindingManifestError(
            "live mount gate executor binding does not match"
        )
    if gate.get("mount_binding_sha256") != mount_sha:
        raise BrokerIdentityRuntimeBindingManifestError(
            "live mount gate mount binding does not match"
        )
    required = {
        "read_only": True,
        "mount_binding_ready": True,
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
        if gate.get(field) is not expected:
            raise BrokerIdentityRuntimeBindingManifestError(
                f"live mount gate safety flag failed: {field}"
            )
    return driver_sha, contract_sha, skeleton_sha, mount_sha


def capture_runtime_binding_manifest(
    driver_contract_file: str | Path,
    executor_contract_file: str | Path,
    live_mount_gate_file: str | Path,
    output_directory: str | Path,
    *,
    runner: Runner | None = None,
    now: datetime | None = None,
    driver_verifier: DriverVerifier = verify_production_driver_contract,
    executor_verifier: ExecutorVerifier = verify_production_executor_contract,
) -> dict[str, object]:
    driver = _read_private_json(
        Path(driver_contract_file).expanduser().resolve(),
        "production driver contract",
    )
    executor = _read_private_json(
        Path(executor_contract_file).expanduser().resolve(),
        "production executor contract",
    )
    gate = _read_private_json(
        Path(live_mount_gate_file).expanduser().resolve(),
        "live mount gate",
    )
    driver_sha, contract_sha, skeleton_sha, mount_sha = _validate_inputs(
        driver,
        executor,
        gate,
        driver_verifier=driver_verifier,
        executor_verifier=executor_verifier,
    )

    command_runner = runner or SubprocessRunner()
    document = _inspect_mosquitto(command_runner)
    runtime = _runtime_identity(document)
    config_source = _single_bind_mount(document, "/mosquitto/config")
    data_source = _single_bind_mount(document, "/mosquitto/data")
    if config_source == data_source:
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto config and data sources must be distinct"
        )
    working, compose_files = _compose_binding(document)
    if (
        not config_source.is_relative_to(working)
        or not data_source.is_relative_to(working)
    ):
        raise BrokerIdentityRuntimeBindingManifestError(
            "live Mosquitto sources are outside the Compose deployment"
        )

    mount_binding = {
        "image_id": runtime["image_id"],
        "image_ref": runtime["image_ref"],
        "compose_working_directory": str(working),
        "compose_config_files": [str(path) for path in compose_files],
        "config_source": str(config_source),
        "data_source": str(data_source),
    }
    if _sha256_text(_canonical_json(mount_binding)) != mount_sha:
        raise BrokerIdentityRuntimeBindingManifestError(
            "live runtime mount binding no longer matches the gate"
        )

    source_binding = executor.get("source_binding")
    baseline_sha = (
        source_binding.get("baseline_broker_config_sha256")
        if isinstance(source_binding, dict)
        else None
    )
    baseline_sha = _require_sha256(baseline_sha, "baseline Broker config")
    config_file = config_source / "mosquitto.conf"
    state_file = data_source / "dynamic-security.json"
    if not config_file.is_file() or config_file.is_symlink():
        raise BrokerIdentityRuntimeBindingManifestError(
            "live host mosquitto.conf is missing or unsafe"
        )
    if _sha256_path(config_file) != baseline_sha:
        raise BrokerIdentityRuntimeBindingManifestError(
            "live host mosquitto.conf has drifted from the contract"
        )
    if state_file.exists():
        raise BrokerIdentityRuntimeBindingManifestError(
            "live host Dynamic Security state already exists"
        )

    output = _private_output_directory(Path(output_directory).expanduser())
    protected_roots = (working, config_source, data_source)
    if any(output == root or output.is_relative_to(root) for root in protected_roots):
        raise BrokerIdentityRuntimeBindingManifestError(
            "runtime binding output directory overlaps the live deployment"
        )

    observed = (now or datetime.now(UTC)).astimezone(UTC)
    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "created_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "driver_contract_sha256": driver_sha,
        "contract_sha256": contract_sha,
        "skeleton_sha256": skeleton_sha,
        "mount_binding_sha256": mount_sha,
        "runtime": runtime,
        "paths": {
            "compose_working_directory": str(working),
            "compose_config_files": [str(path) for path in compose_files],
            "config_source": str(config_source),
            "data_source": str(data_source),
            "config_file": str(config_file),
            "dynamic_security_state_file": str(state_file),
        },
        "path_identity": {
            "compose_working_directory": _path_identity(working),
            "compose_config_files": [
                _path_identity(path, include_sha256=True) for path in compose_files
            ],
            "config_source": _path_identity(config_source),
            "data_source": _path_identity(data_source),
            "config_file": _path_identity(config_file, include_sha256=True),
        },
        "baseline_config_sha256": baseline_sha,
        "dynamic_security_state_absent": True,
        "read_only_capture": True,
        "private_manifest": True,
        "path_values_redacted_from_stdout": True,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    manifest["manifest_sha256"] = _sha256_document(manifest)
    destination = output / (
        "broker-runtime-binding-"
        f"{str(runtime['container_id'])[:12]}-"
        f"{observed.strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    if destination.exists():
        raise BrokerIdentityRuntimeBindingManifestError(
            "runtime binding manifest destination already exists"
        )
    _atomic_private_write(destination, _canonical_json(manifest) + "\n")
    verify_runtime_binding_manifest(destination)
    return {
        "schema": SUMMARY_SCHEMA,
        "runtime_binding_file": destination.name,
        "output_directory_fingerprint": _sha256_text(str(output))[:16],
        "driver_contract_sha256": driver_sha,
        "contract_sha256": contract_sha,
        "mount_binding_sha256": mount_sha,
        "manifest_sha256": manifest["manifest_sha256"],
        "runtime_binding_captured": True,
        "read_only_capture": True,
        "path_values_redacted_from_stdout": True,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def verify_runtime_binding_manifest(
    manifest_file: str | Path,
) -> dict[str, object]:
    manifest = _read_private_json(
        Path(manifest_file).expanduser().resolve(),
        "runtime binding manifest",
    )
    if manifest.get("schema") != SCHEMA:
        raise BrokerIdentityRuntimeBindingManifestError(
            "runtime binding manifest schema is invalid"
        )
    digest = _require_sha256(
        manifest.get("manifest_sha256"),
        "runtime binding manifest",
    )
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if _sha256_document(unsigned) != digest:
        raise BrokerIdentityRuntimeBindingManifestError(
            "runtime binding manifest fingerprint does not match"
        )
    for field in (
        "driver_contract_sha256",
        "contract_sha256",
        "skeleton_sha256",
        "mount_binding_sha256",
        "baseline_config_sha256",
    ):
        _require_sha256(manifest.get(field), field)
    required = {
        "dynamic_security_state_absent": True,
        "read_only_capture": True,
        "private_manifest": True,
        "path_values_redacted_from_stdout": True,
        "production_driver_installed": False,
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
        if manifest.get(field) is not expected:
            raise BrokerIdentityRuntimeBindingManifestError(
                f"runtime binding manifest safety flag failed: {field}"
            )
    paths = manifest.get("paths")
    if not isinstance(paths, dict):
        raise BrokerIdentityRuntimeBindingManifestError(
            "runtime binding manifest path inventory is missing"
        )
    required_paths = (
        "compose_working_directory",
        "config_source",
        "data_source",
        "config_file",
        "dynamic_security_state_file",
    )
    for field in required_paths:
        value = paths.get(field)
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise BrokerIdentityRuntimeBindingManifestError(
                f"runtime binding manifest path is invalid: {field}"
            )
    return {
        "schema": SCHEMA,
        "manifest_sha256": digest,
        "verified": True,
        "runtime_binding_captured": True,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "current_services_modified": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture a private, read-only real-T1 Mosquitto runtime binding "
            "manifest without modifying any running service."
        )
    )
    parser.add_argument("driver_contract_file")
    parser.add_argument("executor_contract_file")
    parser.add_argument("live_mount_gate_file")
    parser.add_argument("output_directory")
    args = parser.parse_args(argv)
    try:
        report = capture_runtime_binding_manifest(
            args.driver_contract_file,
            args.executor_contract_file,
            args.live_mount_gate_file,
            args.output_directory,
        )
    except (
        BrokerIdentityProductionDriverContractError,
        BrokerIdentityProductionExecutorContractError,
        BrokerIdentityRuntimeBindingManifestError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker runtime binding capture failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
