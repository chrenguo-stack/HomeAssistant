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

from .t1_broker_identity_production_driver_contract import (
    BrokerIdentityProductionDriverContractError,
    verify_production_driver_contract,
)
from .t1_broker_identity_production_driver_preflight import (
    BrokerIdentityProductionDriverPreflightError,
    verify_production_driver_preflight,
)
from .t1_broker_identity_production_executor_contract import (
    BrokerIdentityProductionExecutorContractError,
    verify_production_executor_contract,
)
from .t1_broker_identity_runtime_binding_manifest import (
    BrokerIdentityRuntimeBindingManifestError,
    verify_runtime_binding_manifest,
)

SCHEMA = "gh.m2.t1-broker-identity-activation-readiness-bundle/1"
SUMMARY_SCHEMA = "gh.m2.t1-broker-identity-activation-readiness-summary/1"
HA_GATE_SCHEMA = "gh.m2.t1-homeassistant-mqtt-target-gate/1"
_OUTPUT_PREFIX = "greenhouse-m2-runtime-bindings-"
_ALLOWED_TARGET_KINDS = frozenset(
    {"docker_service_alias", "loopback", "host_address"}
)
_REQUIRED_BLOCKERS = (
    "explicit_operator_decision_required",
    "production_driver_not_installed",
    "single_use_authorization_not_created",
    "homeassistant_official_mqtt_ui_config_flow_pending",
    "real_node_credential_delivery_unverified",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{16}$")

DriverVerifier = Callable[[dict[str, object]], dict[str, object]]
ExecutorVerifier = Callable[[dict[str, object]], dict[str, object]]
ManifestVerifier = Callable[[str | Path], dict[str, object]]
PreflightVerifier = Callable[[dict[str, object]], dict[str, object]]


class BrokerIdentityActivationReadinessBundleError(RuntimeError):
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


def _sha256_document(document: dict[str, object]) -> str:
    return _sha256_text(_canonical_json(document))


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise BrokerIdentityActivationReadinessBundleError(
            f"{label} fingerprint is invalid"
        )
    return value


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityActivationReadinessBundleError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityActivationReadinessBundleError(
            f"{label} is invalid"
        ) from error
    if not isinstance(document, dict):
        raise BrokerIdentityActivationReadinessBundleError(
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
        raise BrokerIdentityActivationReadinessBundleError(
            "activation readiness output directory name is not allowed"
        )
    if path.exists() and path.is_symlink():
        raise BrokerIdentityActivationReadinessBundleError(
            "activation readiness output directory is unsafe"
        )
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved = path.resolve()
    if resolved.is_symlink() or resolved.stat().st_mode & 0o077:
        raise BrokerIdentityActivationReadinessBundleError(
            "activation readiness output directory must be private"
        )
    return resolved


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BrokerIdentityActivationReadinessBundleError(
            "runtime binding creation timestamp is invalid"
        )
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise BrokerIdentityActivationReadinessBundleError(
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
        raise BrokerIdentityActivationReadinessBundleError(
            "runtime binding creation timestamp is in the future"
        )
    if age > max_age_seconds:
        raise BrokerIdentityActivationReadinessBundleError(
            "runtime binding manifest is stale"
        )


def _validate_homeassistant_gate(
    gate: dict[str, object],
) -> tuple[str, str, str, str, str]:
    required = {
        "schema": HA_GATE_SCHEMA,
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "prior_audit_complete": True,
        "target_model_ready": True,
        "ready_for_operator_reconfigure": False,
        "ready_for_live_apply": False,
    }
    for field, expected in required.items():
        if gate.get(field) != expected:
            raise BrokerIdentityActivationReadinessBundleError(
                f"Home Assistant target gate failed: {field}"
            )
    target_kind = gate.get("selected_target_kind")
    target_fingerprint = gate.get("selected_target_fingerprint")
    if target_kind not in _ALLOWED_TARGET_KINDS:
        raise BrokerIdentityActivationReadinessBundleError(
            "Home Assistant target kind is invalid"
        )
    if (
        not isinstance(target_fingerprint, str)
        or _FINGERPRINT.fullmatch(target_fingerprint) is None
    ):
        raise BrokerIdentityActivationReadinessBundleError(
            "Home Assistant target fingerprint is invalid"
        )
    official = gate.get("homeassistant_official_reconfigure")
    if not isinstance(official, dict):
        raise BrokerIdentityActivationReadinessBundleError(
            "Home Assistant official reconfigure section is missing"
        )
    official_required = {
        "official_config_flow_only": True,
        "direct_storage_edit_forbidden": True,
        "automatic_apply": False,
        "operator_action_required": True,
        "operator_action_authorized": False,
        "staged_material_complete": True,
        "discovery_preserved": True,
        "retained_baseline_readable": True,
        "post_change_reaudit_required": True,
        "rollback_via_official_reconfigure_or_fresh_backup": True,
    }
    for field, expected in official_required.items():
        if official.get(field) is not expected:
            raise BrokerIdentityActivationReadinessBundleError(
                f"Home Assistant official reconfigure gate failed: {field}"
            )
    entry_fingerprint = official.get("pre_change_entry_fingerprint")
    storage_sha256 = official.get("pre_change_storage_sha256")
    if (
        not isinstance(entry_fingerprint, str)
        or _FINGERPRINT.fullmatch(entry_fingerprint) is None
    ):
        raise BrokerIdentityActivationReadinessBundleError(
            "Home Assistant entry fingerprint is invalid"
        )
    storage_sha256 = _require_sha256(
        storage_sha256,
        "Home Assistant storage",
    )
    blockers = gate.get("activation_blockers")
    required_blockers = {
        "broker_identity_not_activated",
        "homeassistant_operator_reconfigure_required",
        "node_credential_delivery_path_unverified",
    }
    if not isinstance(blockers, list) or not required_blockers.issubset(blockers):
        raise BrokerIdentityActivationReadinessBundleError(
            "Home Assistant target gate blockers are incomplete"
        )
    return (
        str(target_kind),
        target_fingerprint,
        entry_fingerprint,
        storage_sha256,
        _sha256_document(gate),
    )


def _validate_input_directory(paths: Sequence[Path], output: Path) -> None:
    parents = {path.parent for path in paths}
    if len(parents) != 1 or next(iter(parents)) != output:
        raise BrokerIdentityActivationReadinessBundleError(
            "activation readiness inputs must share the private output directory"
        )


def build_activation_readiness_bundle(
    driver_contract_file: str | Path,
    executor_contract_file: str | Path,
    runtime_binding_manifest_file: str | Path,
    production_driver_preflight_file: str | Path,
    homeassistant_target_gate_file: str | Path,
    output_directory: str | Path,
    *,
    max_manifest_age_seconds: int = 1800,
    now: datetime | None = None,
    driver_verifier: DriverVerifier = verify_production_driver_contract,
    executor_verifier: ExecutorVerifier = verify_production_executor_contract,
    manifest_verifier: ManifestVerifier = verify_runtime_binding_manifest,
    preflight_verifier: PreflightVerifier = verify_production_driver_preflight,
) -> dict[str, object]:
    output = _private_output_directory(Path(output_directory).expanduser())
    paths = tuple(
        Path(value).expanduser().resolve()
        for value in (
            driver_contract_file,
            executor_contract_file,
            runtime_binding_manifest_file,
            production_driver_preflight_file,
            homeassistant_target_gate_file,
        )
    )
    _validate_input_directory(paths, output)
    driver_path, executor_path, manifest_path, preflight_path, ha_gate_path = paths
    driver = _read_private_json(driver_path, "production driver contract")
    executor = _read_private_json(executor_path, "production executor contract")
    manifest = _read_private_json(manifest_path, "runtime binding manifest")
    preflight = _read_private_json(preflight_path, "production driver preflight")
    ha_gate = _read_private_json(ha_gate_path, "Home Assistant target gate")

    driver_result = driver_verifier(driver)
    executor_result = executor_verifier(executor)
    manifest_result = manifest_verifier(manifest_path)
    preflight_result = preflight_verifier(preflight)
    if driver_result.get("verified") is not True:
        raise BrokerIdentityActivationReadinessBundleError(
            "production driver contract verification is incomplete"
        )
    if executor_result.get("verified") is not True:
        raise BrokerIdentityActivationReadinessBundleError(
            "production executor contract verification is incomplete"
        )
    if manifest_result.get("verified") is not True:
        raise BrokerIdentityActivationReadinessBundleError(
            "runtime binding manifest verification is incomplete"
        )
    if preflight_result.get("verified") is not True:
        raise BrokerIdentityActivationReadinessBundleError(
            "production driver preflight verification is incomplete"
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
    preflight_sha = _require_sha256(
        preflight_result.get("preflight_sha256"),
        "production driver preflight",
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
        or preflight.get("driver_contract_sha256") != driver_sha
        or preflight.get("contract_sha256") != contract_sha
        or preflight.get("mount_binding_sha256") != mount_sha
        or preflight.get("runtime_binding_manifest_sha256") != manifest_sha
    ):
        raise BrokerIdentityActivationReadinessBundleError(
            "activation readiness input binding does not match"
        )
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    _validate_manifest_age(
        manifest,
        now=observed,
        max_age_seconds=max_manifest_age_seconds,
    )
    (
        target_kind,
        target_fingerprint,
        entry_fingerprint,
        storage_sha256,
        ha_gate_sha,
    ) = _validate_homeassistant_gate(ha_gate)
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        raise BrokerIdentityActivationReadinessBundleError(
            "runtime binding identity is missing"
        )
    runtime_fingerprint = _sha256_document(
        {
            "container_id": runtime.get("container_id"),
            "image_id": runtime.get("image_id"),
            "started_at": runtime.get("started_at"),
            "restart_count": runtime.get("restart_count"),
        }
    )[:16]

    bundle: dict[str, object] = {
        "schema": SCHEMA,
        "created_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "driver_contract_sha256": driver_sha,
        "contract_sha256": contract_sha,
        "mount_binding_sha256": mount_sha,
        "runtime_binding_manifest_sha256": manifest_sha,
        "production_driver_preflight_sha256": preflight_sha,
        "homeassistant_target_gate_sha256": ha_gate_sha,
        "broker_runtime_fingerprint": runtime_fingerprint,
        "homeassistant_binding": {
            "target_kind": target_kind,
            "target_fingerprint": target_fingerprint,
            "entry_fingerprint": entry_fingerprint,
            "storage_sha256": storage_sha256,
        },
        "activation_scope": {
            "broker_identity_activation_only": True,
            "preserve_anonymous": True,
            "anonymous_closure_in_transaction": False,
            "homeassistant_reconfigure_in_transaction": False,
            "node_credential_delivery_in_transaction": False,
            "successful_activation_restart_count": 1,
            "rollback_may_require_additional_restart": True,
        },
        "blockers": list(_REQUIRED_BLOCKERS),
        "readiness_bundle_complete": True,
        "operator_decision_required": True,
        "single_use_authorization_created": False,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "path_values_redacted": True,
        "secret_values_included": False,
    }
    bundle["bundle_sha256"] = _sha256_document(bundle)
    destination = output / (
        "broker-activation-readiness-"
        f"{observed.strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    if destination.exists():
        raise BrokerIdentityActivationReadinessBundleError(
            "activation readiness bundle destination already exists"
        )
    _atomic_private_write(destination, _canonical_json(bundle) + "\n")
    return {
        "schema": SUMMARY_SCHEMA,
        "activation_readiness_file": destination.name,
        "bundle_sha256": bundle["bundle_sha256"],
        "broker_runtime_fingerprint": runtime_fingerprint,
        "target_kind": target_kind,
        "target_fingerprint": target_fingerprint,
        "readiness_bundle_complete": True,
        "operator_decision_required": True,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "path_values_redacted": True,
        "secret_values_included": False,
    }


def verify_activation_readiness_bundle(
    bundle: dict[str, object],
) -> dict[str, object]:
    if bundle.get("schema") != SCHEMA:
        raise BrokerIdentityActivationReadinessBundleError(
            "activation readiness bundle schema is invalid"
        )
    digest = _require_sha256(
        bundle.get("bundle_sha256"),
        "activation readiness bundle",
    )
    unsigned = dict(bundle)
    unsigned.pop("bundle_sha256", None)
    if _sha256_document(unsigned) != digest:
        raise BrokerIdentityActivationReadinessBundleError(
            "activation readiness bundle fingerprint does not match"
        )
    for field in (
        "driver_contract_sha256",
        "contract_sha256",
        "mount_binding_sha256",
        "runtime_binding_manifest_sha256",
        "production_driver_preflight_sha256",
        "homeassistant_target_gate_sha256",
    ):
        _require_sha256(bundle.get(field), field)
    required = {
        "readiness_bundle_complete": True,
        "operator_decision_required": True,
        "single_use_authorization_created": False,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "path_values_redacted": True,
        "secret_values_included": False,
    }
    for field, expected in required.items():
        if bundle.get(field) is not expected:
            raise BrokerIdentityActivationReadinessBundleError(
                f"activation readiness bundle safety flag failed: {field}"
            )
    if bundle.get("blockers") != list(_REQUIRED_BLOCKERS):
        raise BrokerIdentityActivationReadinessBundleError(
            "activation readiness bundle blockers have drifted"
        )
    scope = bundle.get("activation_scope")
    if not isinstance(scope, dict) or scope != {
        "broker_identity_activation_only": True,
        "preserve_anonymous": True,
        "anonymous_closure_in_transaction": False,
        "homeassistant_reconfigure_in_transaction": False,
        "node_credential_delivery_in_transaction": False,
        "successful_activation_restart_count": 1,
        "rollback_may_require_additional_restart": True,
    }:
        raise BrokerIdentityActivationReadinessBundleError(
            "activation readiness scope has drifted"
        )
    return {
        "schema": SCHEMA,
        "bundle_sha256": digest,
        "verified": True,
        "operator_decision_required": True,
        "production_driver_installed": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "current_services_modified": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bind the verified real-T1 production preflight and Home Assistant "
            "target into a private, non-authorizing activation readiness bundle."
        )
    )
    parser.add_argument("driver_contract_file")
    parser.add_argument("executor_contract_file")
    parser.add_argument("runtime_binding_manifest_file")
    parser.add_argument("production_driver_preflight_file")
    parser.add_argument("homeassistant_target_gate_file")
    parser.add_argument("output_directory")
    parser.add_argument("--max-manifest-age-seconds", type=int, default=1800)
    args = parser.parse_args(argv)
    try:
        result = build_activation_readiness_bundle(
            args.driver_contract_file,
            args.executor_contract_file,
            args.runtime_binding_manifest_file,
            args.production_driver_preflight_file,
            args.homeassistant_target_gate_file,
            args.output_directory,
            max_manifest_age_seconds=args.max_manifest_age_seconds,
        )
    except (
        BrokerIdentityActivationReadinessBundleError,
        BrokerIdentityProductionDriverContractError,
        BrokerIdentityProductionDriverPreflightError,
        BrokerIdentityProductionExecutorContractError,
        BrokerIdentityRuntimeBindingManifestError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker activation readiness bundle failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
