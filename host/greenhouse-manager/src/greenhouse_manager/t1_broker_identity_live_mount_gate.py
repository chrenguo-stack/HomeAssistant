from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from .t1_backup import BackupError, verify_backup
from .t1_broker_identity_activation_checks import (
    BrokerIdentityActivationCheckError,
    BrokerIdentityActivationHandoffError,
    Runner,
    runtime_healthy,
    runtime_summary,
)
from .t1_broker_identity_production_executor_contract import (
    BrokerIdentityProductionExecutorContractError,
    build_production_executor_contract,
    verify_production_executor_contract,
)
from .t1_migration_stage import MigrationStageError
from .t1_shadow import SubprocessRunner

SCHEMA = "gh.m2.t1-broker-identity-live-mount-gate/1"
ContractBuilder = Callable[..., dict[str, object]]
ContractVerifier = Callable[[dict[str, object]], dict[str, object]]
BackupVerifier = Callable[[str | Path], dict[str, Any]]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE_PREFIXES = (
    "gh-m2-restore-",
    "gh-m2-shadow-",
    "gh-m2-shadow-services-",
    "gh-m2-package-rehearsal-",
    "gh-m2-stage-fault-",
    "gh-m2-stage-rehearsal-",
    "gh-m2-isolated-",
)


class BrokerIdentityLiveMountGateError(RuntimeError):
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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityLiveMountGateError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityLiveMountGateError(f"{label} is invalid") from error
    if not isinstance(value, dict):
        raise BrokerIdentityLiveMountGateError(f"{label} must be an object")
    return value


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise BrokerIdentityLiveMountGateError(f"{label} path is missing")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise BrokerIdentityLiveMountGateError(f"{label} path is unsafe")
    return path


def _require_success(
    runner: Runner,
    command: Sequence[str],
    message: str,
) -> str:
    code, output = runner.run(tuple(command))
    if code != 0:
        raise BrokerIdentityLiveMountGateError(message)
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
        raise BrokerIdentityLiveMountGateError(
            "live Mosquitto inspect returned invalid JSON"
        ) from error
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
        raise BrokerIdentityLiveMountGateError(
            "live Mosquitto inspect returned an unexpected document"
        )
    return values[0]


def _single_bind_mount(document: dict[str, Any], destination: str) -> Path:
    mounts = document.get("Mounts")
    if not isinstance(mounts, list):
        raise BrokerIdentityLiveMountGateError("live Mosquitto mount inventory is missing")
    matches = [
        item
        for item in mounts
        if isinstance(item, dict) and item.get("Destination") == destination
    ]
    if len(matches) != 1:
        raise BrokerIdentityLiveMountGateError(
            f"live Mosquitto must have one {destination} mount"
        )
    mount = matches[0]
    if mount.get("Type") != "bind" or mount.get("RW") is not True:
        raise BrokerIdentityLiveMountGateError(
            f"live Mosquitto {destination} mount must be a writable bind mount"
        )
    source = mount.get("Source")
    if not isinstance(source, str) or not source:
        raise BrokerIdentityLiveMountGateError(
            f"live Mosquitto {destination} source is missing"
        )
    path = Path(source).expanduser()
    if not path.is_absolute():
        raise BrokerIdentityLiveMountGateError(
            f"live Mosquitto {destination} source is not absolute"
        )
    if path.is_symlink():
        raise BrokerIdentityLiveMountGateError(
            f"live Mosquitto {destination} source is unsafe"
        )
    path = path.resolve()
    if not path.is_dir():
        raise BrokerIdentityLiveMountGateError(
            f"live Mosquitto {destination} source is unsafe"
        )
    return path


def _compose_binding(document: dict[str, Any]) -> tuple[Path, tuple[Path, ...]]:
    config = document.get("Config")
    if not isinstance(config, dict):
        raise BrokerIdentityLiveMountGateError("live Mosquitto config metadata is missing")
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        raise BrokerIdentityLiveMountGateError("live Mosquitto Compose labels are missing")
    raw_working = labels.get("com.docker.compose.project.working_dir")
    raw_files = labels.get("com.docker.compose.project.config_files")
    if not isinstance(raw_working, str) or not raw_working.strip():
        raise BrokerIdentityLiveMountGateError(
            "live Mosquitto Compose working directory is missing"
        )
    if not isinstance(raw_files, str) or not raw_files.strip():
        raise BrokerIdentityLiveMountGateError(
            "live Mosquitto Compose config file binding is missing"
        )
    raw_working_path = Path(raw_working).expanduser()
    if raw_working_path.is_symlink():
        raise BrokerIdentityLiveMountGateError(
            "live Mosquitto Compose working directory is unsafe"
        )
    working = raw_working_path.resolve()
    if not working.is_dir():
        raise BrokerIdentityLiveMountGateError(
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
            raise BrokerIdentityLiveMountGateError(
                "live Mosquitto Compose config file binding is unsafe"
            )
        path = path.resolve()
        if not path.is_file() or not path.is_relative_to(working):
            raise BrokerIdentityLiveMountGateError(
                "live Mosquitto Compose config file binding is unsafe"
            )
        files.append(path)
    if not files:
        raise BrokerIdentityLiveMountGateError(
            "live Mosquitto Compose config file binding is empty"
        )
    return working, tuple(files)


def _runtime_identity(document: dict[str, Any]) -> tuple[str, str]:
    state = document.get("State")
    if not isinstance(state, dict) or state.get("Status") != "running":
        raise BrokerIdentityLiveMountGateError("live Mosquitto is not running")
    if int(document.get("RestartCount", -1)) != 0:
        raise BrokerIdentityLiveMountGateError(
            "live Mosquitto restart count is not zero"
        )
    image_id = document.get("Image")
    config = document.get("Config")
    image_ref = config.get("Image") if isinstance(config, dict) else None
    if not isinstance(image_id, str) or not image_id:
        raise BrokerIdentityLiveMountGateError("live Mosquitto image ID is missing")
    if not isinstance(image_ref, str) or not image_ref:
        raise BrokerIdentityLiveMountGateError("live Mosquitto image ref is missing")
    return image_id, image_ref


def _active_config_lines(config: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in config.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _validate_live_broker(
    runner: Runner,
    *,
    expected_config_sha256: str,
    expected_retained_topic: str,
) -> dict[str, bool]:
    config = _require_success(
        runner,
        (
            "docker",
            "exec",
            "mosquitto",
            "sh",
            "-c",
            "test -r /mosquitto/config/mosquitto.conf && "
            "cat /mosquitto/config/mosquitto.conf",
        ),
        "live mosquitto.conf cannot be read",
    )
    lines = _active_config_lines(config)
    anonymous = any(
        line.lower()
        in {
            "allow_anonymous true",
            "allow_anonymous yes",
            "allow_anonymous 1",
            "allow_anonymous on",
        }
        for line in lines
    )
    plugin_absent = not any(
        line.startswith(("plugin ", "global_plugin ", "auth_plugin "))
        for line in lines
    )
    config_bound = _sha256_bytes(config.encode("utf-8")) == expected_config_sha256
    state_code, _state_output = runner.run(
        (
            "docker",
            "exec",
            "mosquitto",
            "sh",
            "-c",
            "test ! -e /mosquitto/data/dynamic-security.json",
        )
    )
    retained_code, retained = runner.run(
        (
            "docker",
            "exec",
            "mosquitto",
            "mosquitto_sub",
            "-h",
            "127.0.0.1",
            "-V",
            "5",
            "-C",
            "1",
            "-W",
            "5",
            "-F",
            "%p",
            "-t",
            expected_retained_topic,
        )
    )
    checks = {
        "live_config_bound": config_bound,
        "anonymous_compatibility_enabled": anonymous,
        "dynamic_security_plugin_absent": plugin_absent,
        "dynamic_security_state_absent": state_code == 0,
        "anonymous_retained_state_readable": retained_code == 0
        and bool(retained.strip()),
    }
    if not all(checks.values()):
        failed = next(name for name, value in checks.items() if not value)
        raise BrokerIdentityLiveMountGateError(
            f"live Broker mount gate failed: {failed}"
        )
    return checks


def _candidate_residue_absent(runner: Runner) -> bool:
    output = _require_success(
        runner,
        ("docker", "ps", "-a", "--format", "{{.Names}}"),
        "Docker container inventory cannot be read",
    )
    return not any(
        name.startswith(_CANDIDATE_PREFIXES)
        for name in (line.strip() for line in output.splitlines())
        if name
    )


def build_live_mount_gate(
    contract_file: str | Path,
    handoff_directory: str | Path,
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    runner: Runner | None = None,
    contract_builder: ContractBuilder = build_production_executor_contract,
    contract_verifier: ContractVerifier = verify_production_executor_contract,
    backup_verifier: BackupVerifier = verify_backup,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    command_runner = runner or SubprocessRunner()
    contract_path = Path(contract_file).expanduser().resolve()
    handoff = Path(handoff_directory).expanduser().resolve()
    stage = Path(stage_directory).expanduser().resolve()
    contract = _read_private_json(contract_path, "production executor contract")
    verified = contract_verifier(contract)
    digest = verified.get("contract_sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise BrokerIdentityLiveMountGateError(
            "production executor contract verification is incomplete"
        )
    rebuilt = contract_builder(handoff, stage)
    if rebuilt.get("contract_sha256") != digest or rebuilt != contract:
        raise BrokerIdentityLiveMountGateError(
            "production executor contract does not match current handoff and stage"
        )

    manifest = _read_private_json(handoff / "manifest.json", "activation handoff manifest")
    fresh = manifest.get("fresh_rollback")
    if not isinstance(fresh, dict):
        raise BrokerIdentityLiveMountGateError("fresh rollback record is missing")
    rollback_relative = _safe_relative(fresh.get("path"), "fresh rollback")
    rollback = handoff.joinpath(*rollback_relative.parts)
    backup = backup_verifier(rollback)
    expected_image = (
        backup.get("sources", {}).get("mosquitto", {}).get("image_id")
        if isinstance(backup.get("sources"), dict)
        else None
    )
    if not isinstance(expected_image, str) or not expected_image:
        raise BrokerIdentityLiveMountGateError(
            "fresh rollback Mosquitto image binding is missing"
        )

    document = _inspect_mosquitto(command_runner)
    image_id, image_ref = _runtime_identity(document)
    if image_id != expected_image:
        raise BrokerIdentityLiveMountGateError(
            "live Mosquitto image does not match fresh rollback"
        )
    config_source = _single_bind_mount(document, "/mosquitto/config")
    data_source = _single_bind_mount(document, "/mosquitto/data")
    if config_source == data_source:
        raise BrokerIdentityLiveMountGateError(
            "live Mosquitto config and data mounts must be distinct"
        )
    working, compose_files = _compose_binding(document)
    if (
        not config_source.is_relative_to(working)
        or not data_source.is_relative_to(working)
    ):
        raise BrokerIdentityLiveMountGateError(
            "live Mosquitto mount sources are outside the Compose deployment"
        )

    source_binding = contract.get("source_binding")
    expected_config_sha = (
        source_binding.get("baseline_broker_config_sha256")
        if isinstance(source_binding, dict)
        else None
    )
    if not isinstance(expected_config_sha, str) or _SHA256.fullmatch(
        expected_config_sha
    ) is None:
        raise BrokerIdentityLiveMountGateError(
            "production executor contract Broker binding is missing"
        )
    broker_checks = _validate_live_broker(
        command_runner,
        expected_config_sha256=expected_config_sha,
        expected_retained_topic=expected_retained_topic,
    )
    runtime = runtime_summary(command_runner)
    if not runtime_healthy(runtime):
        raise BrokerIdentityLiveMountGateError(
            "required service runtime is not healthy"
        )
    residue_absent = _candidate_residue_absent(command_runner)
    if not residue_absent:
        raise BrokerIdentityLiveMountGateError(
            "temporary M2 candidate container residue is present"
        )

    mount_binding = {
        "image_id": image_id,
        "image_ref": image_ref,
        "compose_working_directory": str(working),
        "compose_config_files": [str(path) for path in compose_files],
        "config_source": str(config_source),
        "data_source": str(data_source),
    }
    mount_digest = _sha256_text(_canonical_json(mount_binding))
    checks = {
        "contract_verified_and_rebuilt": True,
        "fresh_rollback_image_bound": True,
        "mosquitto_running_zero_restart": True,
        "config_bind_mount_private_scope": True,
        "data_bind_mount_private_scope": True,
        "compose_source_bound": True,
        **broker_checks,
        "required_services_running_zero_restart": True,
        "candidate_residue_absent": True,
    }
    return {
        "schema": SCHEMA,
        "read_only": True,
        "contract_sha256": digest,
        "mount_binding_sha256": mount_digest,
        "mount_binding": {
            "image_id": image_id,
            "image_ref_fingerprint": _sha256_text(image_ref)[:16],
            "compose_working_directory_fingerprint": _sha256_text(str(working))[
                :16
            ],
            "compose_config_file_fingerprints": [
                _sha256_text(str(path))[:16] for path in compose_files
            ],
            "config_source_fingerprint": _sha256_text(str(config_source))[:16],
            "data_source_fingerprint": _sha256_text(str(data_source))[:16],
        },
        "checks": checks,
        "runtime": runtime,
        "mount_binding_ready": all(checks.values()),
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Runner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only real-T1 Mosquitto mount binding gate for the "
            "disabled production executor contract."
        )
    )
    parser.add_argument("contract_file")
    parser.add_argument("handoff_directory")
    parser.add_argument("stage_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    args = parser.parse_args(argv)
    try:
        result = build_live_mount_gate(
            args.contract_file,
            args.handoff_directory,
            args.stage_directory,
            expected_retained_topic=args.expected_retained_topic,
            runner=runner,
        )
    except (
        BackupError,
        BrokerIdentityActivationCheckError,
        BrokerIdentityActivationHandoffError,
        BrokerIdentityLiveMountGateError,
        BrokerIdentityProductionExecutorContractError,
        MigrationStageError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker live mount gate failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["mount_binding_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
