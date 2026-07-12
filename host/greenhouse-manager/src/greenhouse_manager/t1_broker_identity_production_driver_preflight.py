from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .t1_broker_identity_activation_checks import Runner
from .t1_broker_identity_live_mount_gate import build_live_mount_gate
from .t1_broker_identity_preactivation_gate import (
    build_broker_identity_preactivation_gate,
)
from .t1_broker_identity_production_driver_contract import (
    verify_production_driver_contract,
)
from .t1_broker_identity_production_executor_contract import (
    build_production_executor_contract,
    verify_production_executor_contract,
)
from .t1_broker_identity_runtime_binding_manifest import (
    verify_runtime_binding_manifest,
)
from .t1_shadow import SubprocessRunner

SCHEMA = "gh.m2.t1-broker-identity-production-driver-preflight/1"
DriverVerifier = Callable[[dict[str, object]], dict[str, object]]
ExecutorVerifier = Callable[[dict[str, object]], dict[str, object]]
ManifestVerifier = Callable[[str | Path], dict[str, object]]
ExecutorBuilder = Callable[..., dict[str, object]]
LiveGateBuilder = Callable[..., dict[str, object]]
PreactivationBuilder = Callable[..., dict[str, object]]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_BLOCKERS = (
    "production_driver_not_installed",
    "explicit_operator_authorization_not_claimed",
    "homeassistant_official_mqtt_ui_config_flow_pending",
    "real_node_credential_delivery_unverified",
)


class BrokerIdentityProductionDriverPreflightError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
        raise BrokerIdentityProductionDriverPreflightError(
            f"{label} fingerprint is invalid"
        )
    return value


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityProductionDriverPreflightError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityProductionDriverPreflightError(
            f"{label} is invalid"
        ) from error
    if not isinstance(document, dict):
        raise BrokerIdentityProductionDriverPreflightError(
            f"{label} must be a JSON object"
        )
    return document


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding creation timestamp is invalid"
        )
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding creation timestamp is invalid"
        ) from error


def _validate_manifest_age(
    manifest: dict[str, object],
    *,
    now: datetime,
    max_age_seconds: int,
) -> None:
    if max_age_seconds < 60 or max_age_seconds > 3600:
        raise ValueError("runtime binding max age must be between 60 and 3600 seconds")
    age = (now - _parse_timestamp(manifest.get("created_at"))).total_seconds()
    if age < -60:
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding creation timestamp is in the future"
        )
    if age > max_age_seconds:
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding manifest is stale"
        )


def _require_success(runner: Runner, command: Sequence[str], message: str) -> str:
    code, output = runner.run(tuple(command))
    if code != 0:
        raise BrokerIdentityProductionDriverPreflightError(message)
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
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto inspect returned invalid JSON"
        ) from error
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto inspect returned an unexpected document"
        )
    return values[0]


def _compose_files(document: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    config = document.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if not isinstance(labels, dict):
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto Compose labels are missing"
        )
    working = labels.get("com.docker.compose.project.working_dir")
    raw_files = labels.get("com.docker.compose.project.config_files")
    if not isinstance(working, str) or not working:
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto Compose working directory is missing"
        )
    if not isinstance(raw_files, str) or not raw_files:
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto Compose config files are missing"
        )
    working_path = Path(working)
    files: list[str] = []
    for raw in raw_files.split(","):
        value = raw.strip()
        if not value:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = working_path / path
        files.append(str(path.resolve()))
    if not files:
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto Compose config file binding is empty"
        )
    return str(working_path.resolve()), tuple(files)


def _mount_sources(document: dict[str, Any]) -> dict[str, str]:
    mounts = document.get("Mounts")
    if not isinstance(mounts, list):
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto mount inventory is missing"
        )
    result: dict[str, str] = {}
    for destination in ("/mosquitto/config", "/mosquitto/data"):
        matches = [
            item
            for item in mounts
            if isinstance(item, dict) and item.get("Destination") == destination
        ]
        if len(matches) != 1:
            raise BrokerIdentityProductionDriverPreflightError(
                f"live Mosquitto must have one {destination} mount"
            )
        mount = matches[0]
        source = mount.get("Source")
        if (
            mount.get("Type") != "bind"
            or mount.get("RW") is not True
            or not isinstance(source, str)
        ):
            raise BrokerIdentityProductionDriverPreflightError(
                f"live Mosquitto {destination} mount binding has drifted"
            )
        result[destination] = str(Path(source).resolve())
    return result


def _path_identity(path: Path, *, include_sha256: bool = False) -> dict[str, object]:
    if not path.is_absolute() or path.is_symlink() or not path.exists():
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding path is missing or unsafe"
        )
    stat = path.stat()
    identity: dict[str, object] = {
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "mode": stat.st_mode & 0o777,
        "uid": stat.st_uid,
        "gid": stat.st_gid,
    }
    if include_sha256:
        if not path.is_file():
            raise BrokerIdentityProductionDriverPreflightError(
                "runtime binding file identity is invalid"
            )
        identity["sha256"] = _sha256_path(path)
    return identity


def _validate_path_record(
    path_value: object,
    expected_identity: object,
    *,
    include_sha256: bool = False,
) -> Path:
    if not isinstance(path_value, str) or not Path(path_value).is_absolute():
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding path value is invalid"
        )
    path = Path(path_value)
    if str(path.resolve()) != path_value:
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding path is not canonical"
        )
    if not isinstance(expected_identity, dict):
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding path identity is missing"
        )
    if _path_identity(path, include_sha256=include_sha256) != expected_identity:
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding path identity has drifted"
        )
    return path


def _validate_live_gate(report: dict[str, object], contract_sha: str, mount_sha: str) -> None:
    required = {
        "schema": "gh.m2.t1-broker-identity-live-mount-gate/1",
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
        if report.get(field) != expected:
            raise BrokerIdentityProductionDriverPreflightError(
                f"current live mount gate failed: {field}"
            )
    if report.get("contract_sha256") != contract_sha:
        raise BrokerIdentityProductionDriverPreflightError(
            "current live mount gate contract binding has drifted"
        )
    if report.get("mount_binding_sha256") != mount_sha:
        raise BrokerIdentityProductionDriverPreflightError(
            "current live mount gate mount binding has drifted"
        )
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise BrokerIdentityProductionDriverPreflightError(
            "current live mount gate checks are not all passing"
        )


def _validate_preactivation(report: dict[str, object]) -> None:
    required = {
        "schema": "gh.m2.t1-broker-identity-preactivation-gate/1",
        "read_only": True,
        "preconditions_ready": True,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if report.get(field) != expected:
            raise BrokerIdentityProductionDriverPreflightError(
                f"current preactivation gate failed: {field}"
            )
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise BrokerIdentityProductionDriverPreflightError(
            "current preactivation checks are not all passing"
        )


def _validate_runtime_against_manifest(
    document: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    runtime = manifest.get("runtime")
    paths = manifest.get("paths")
    identities = manifest.get("path_identity")
    config = document.get("Config")
    state = document.get("State")
    if not all(isinstance(value, dict) for value in (runtime, paths, identities, config, state)):
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding manifest inventory is incomplete"
        )
    expected_runtime = {
        "container_name": "mosquitto",
        "container_id": document.get("Id"),
        "image_id": document.get("Image"),
        "image_ref": config.get("Image"),
        "started_at": state.get("StartedAt"),
        "restart_count": document.get("RestartCount"),
    }
    if state.get("Status") != "running" or expected_runtime != runtime:
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto runtime identity has drifted"
        )

    working, compose_files = _compose_files(document)
    mounts = _mount_sources(document)
    if paths.get("compose_working_directory") != working:
        raise BrokerIdentityProductionDriverPreflightError(
            "live Compose working directory has drifted"
        )
    if tuple(paths.get("compose_config_files", ())) != compose_files:
        raise BrokerIdentityProductionDriverPreflightError(
            "live Compose config files have drifted"
        )
    if paths.get("config_source") != mounts["/mosquitto/config"]:
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto config source has drifted"
        )
    if paths.get("data_source") != mounts["/mosquitto/data"]:
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto data source has drifted"
        )

    _validate_path_record(
        paths.get("compose_working_directory"),
        identities.get("compose_working_directory"),
    )
    expected_compose_identities = identities.get("compose_config_files")
    if not isinstance(expected_compose_identities, list):
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding Compose identity inventory is missing"
        )
    if len(expected_compose_identities) != len(compose_files):
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding Compose identity inventory has drifted"
        )
    for path, expected in zip(compose_files, expected_compose_identities, strict=True):
        _validate_path_record(path, expected, include_sha256=True)
    _validate_path_record(paths.get("config_source"), identities.get("config_source"))
    _validate_path_record(paths.get("data_source"), identities.get("data_source"))
    config_file = _validate_path_record(
        paths.get("config_file"),
        identities.get("config_file"),
        include_sha256=True,
    )
    if _sha256_path(config_file) != manifest.get("baseline_config_sha256"):
        raise BrokerIdentityProductionDriverPreflightError(
            "live Mosquitto baseline config has drifted"
        )
    state_file = paths.get("dynamic_security_state_file")
    if not isinstance(state_file, str) or not Path(state_file).is_absolute():
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding Dynamic Security path is invalid"
        )
    if Path(state_file).exists():
        raise BrokerIdentityProductionDriverPreflightError(
            "live Dynamic Security state appeared before activation"
        )


def build_production_driver_preflight(
    driver_contract_file: str | Path,
    executor_contract_file: str | Path,
    runtime_binding_manifest_file: str | Path,
    handoff_directory: str | Path,
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    expected_target_fingerprint: str,
    expected_entry_fingerprint: str,
    expected_storage_sha256: str,
    expected_target_kind: str = "loopback",
    max_manifest_age_seconds: int = 900,
    runner: Runner | None = None,
    now: datetime | None = None,
    driver_verifier: DriverVerifier = verify_production_driver_contract,
    executor_verifier: ExecutorVerifier = verify_production_executor_contract,
    manifest_verifier: ManifestVerifier = verify_runtime_binding_manifest,
    executor_builder: ExecutorBuilder = build_production_executor_contract,
    live_gate_builder: LiveGateBuilder = build_live_mount_gate,
    preactivation_builder: PreactivationBuilder = build_broker_identity_preactivation_gate,
) -> dict[str, object]:
    driver_path = Path(driver_contract_file).expanduser().resolve()
    executor_path = Path(executor_contract_file).expanduser().resolve()
    manifest_path = Path(runtime_binding_manifest_file).expanduser().resolve()
    handoff = Path(handoff_directory).expanduser().resolve()
    stage = Path(stage_directory).expanduser().resolve()
    driver = _read_private_json(driver_path, "production driver contract")
    executor = _read_private_json(executor_path, "production executor contract")
    manifest = _read_private_json(manifest_path, "runtime binding manifest")

    driver_result = driver_verifier(driver)
    executor_result = executor_verifier(executor)
    manifest_result = manifest_verifier(manifest_path)
    if driver_result.get("verified") is not True:
        raise BrokerIdentityProductionDriverPreflightError(
            "production driver contract verification is incomplete"
        )
    if executor_result.get("verified") is not True:
        raise BrokerIdentityProductionDriverPreflightError(
            "production executor contract verification is incomplete"
        )
    if manifest_result.get("verified") is not True:
        raise BrokerIdentityProductionDriverPreflightError(
            "runtime binding manifest verification is incomplete"
        )
    driver_sha = _require_sha256(
        driver_result.get("driver_contract_sha256"),
        "production driver contract",
    )
    contract_sha = _require_sha256(
        executor_result.get("contract_sha256"),
        "production executor contract",
    )
    manifest_sha = _require_sha256(
        manifest_result.get("manifest_sha256"),
        "runtime binding manifest",
    )
    mount_sha = _require_sha256(
        driver.get("mount_binding_sha256"),
        "production driver mount binding",
    )
    if (
        driver.get("contract_sha256") != contract_sha
        or manifest.get("driver_contract_sha256") != driver_sha
        or manifest.get("contract_sha256") != contract_sha
        or manifest.get("mount_binding_sha256") != mount_sha
    ):
        raise BrokerIdentityProductionDriverPreflightError(
            "production driver preflight input binding does not match"
        )

    observed = (now or datetime.now(UTC)).astimezone(UTC)
    _validate_manifest_age(
        manifest,
        now=observed,
        max_age_seconds=max_manifest_age_seconds,
    )
    if executor_builder(handoff, stage) != executor:
        raise BrokerIdentityProductionDriverPreflightError(
            "production executor contract no longer matches handoff and stage"
        )

    command_runner = runner or SubprocessRunner()
    live_gate = live_gate_builder(
        executor_path,
        handoff,
        stage,
        expected_retained_topic=expected_retained_topic,
        runner=command_runner,
    )
    _validate_live_gate(live_gate, contract_sha, mount_sha)
    preactivation = preactivation_builder(
        handoff,
        stage,
        expected_retained_topic=expected_retained_topic,
        expected_target_fingerprint=expected_target_fingerprint,
        expected_entry_fingerprint=expected_entry_fingerprint,
        expected_storage_sha256=expected_storage_sha256,
        expected_target_kind=expected_target_kind,
        runner=command_runner,
    )
    _validate_preactivation(preactivation)
    _validate_runtime_against_manifest(_inspect_mosquitto(command_runner), manifest)

    checks = {
        "driver_contract_verified": True,
        "executor_contract_verified_and_rebuilt": True,
        "runtime_binding_manifest_verified": True,
        "runtime_binding_manifest_fresh": True,
        "live_mount_gate_repassed": True,
        "preactivation_gate_repassed": True,
        "container_identity_bound": True,
        "compose_binding_bound": True,
        "host_path_identity_bound": True,
        "baseline_config_bound": True,
        "dynamic_security_state_absent": True,
    }
    report: dict[str, object] = {
        "schema": SCHEMA,
        "driver_contract_sha256": driver_sha,
        "contract_sha256": contract_sha,
        "mount_binding_sha256": mount_sha,
        "runtime_binding_manifest_sha256": manifest_sha,
        "checks": checks,
        "preflight_ready": all(checks.values()),
        "read_only": True,
        "path_values_redacted": True,
        "blockers": list(_REQUIRED_BLOCKERS),
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
    report["preflight_sha256"] = _sha256_document(report)
    return report


def verify_production_driver_preflight(report: dict[str, object]) -> dict[str, object]:
    if report.get("schema") != SCHEMA:
        raise BrokerIdentityProductionDriverPreflightError(
            "production driver preflight schema is invalid"
        )
    digest = _require_sha256(
        report.get("preflight_sha256"),
        "production driver preflight",
    )
    unsigned = dict(report)
    unsigned.pop("preflight_sha256", None)
    if _sha256_document(unsigned) != digest:
        raise BrokerIdentityProductionDriverPreflightError(
            "production driver preflight fingerprint does not match"
        )
    for field in (
        "driver_contract_sha256",
        "contract_sha256",
        "mount_binding_sha256",
        "runtime_binding_manifest_sha256",
    ):
        _require_sha256(report.get(field), field)
    required = {
        "preflight_ready": True,
        "read_only": True,
        "path_values_redacted": True,
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
        if report.get(field) is not expected:
            raise BrokerIdentityProductionDriverPreflightError(
                f"production driver preflight safety flag failed: {field}"
            )
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise BrokerIdentityProductionDriverPreflightError(
            "production driver preflight checks are not all passing"
        )
    if report.get("blockers") != list(_REQUIRED_BLOCKERS):
        raise BrokerIdentityProductionDriverPreflightError(
            "production driver preflight blockers have drifted"
        )
    return {
        "schema": SCHEMA,
        "preflight_sha256": digest,
        "verified": True,
        "preflight_ready": True,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "current_services_modified": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Revalidate the private runtime binding, live mount gate and "
            "preactivation gate without enabling production execution."
        )
    )
    parser.add_argument("driver_contract_file")
    parser.add_argument("executor_contract_file")
    parser.add_argument("runtime_binding_manifest_file")
    parser.add_argument("handoff_directory")
    parser.add_argument("stage_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--expected-target-fingerprint", required=True)
    parser.add_argument("--expected-entry-fingerprint", required=True)
    parser.add_argument("--expected-storage-sha256", required=True)
    parser.add_argument("--expected-target-kind", default="loopback")
    parser.add_argument("--max-manifest-age-seconds", type=int, default=900)
    args = parser.parse_args(argv)
    try:
        report = build_production_driver_preflight(
            args.driver_contract_file,
            args.executor_contract_file,
            args.runtime_binding_manifest_file,
            args.handoff_directory,
            args.stage_directory,
            expected_retained_topic=args.expected_retained_topic,
            expected_target_fingerprint=args.expected_target_fingerprint,
            expected_entry_fingerprint=args.expected_entry_fingerprint,
            expected_storage_sha256=args.expected_storage_sha256,
            expected_target_kind=args.expected_target_kind,
            max_manifest_age_seconds=args.max_manifest_age_seconds,
        )
        verify_production_driver_preflight(report)
    except (RuntimeError, OSError, UnicodeError, ValueError) as error:
        print(f"T1 Broker production driver preflight failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
