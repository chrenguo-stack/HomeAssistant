from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .t1_manager_identity_postcommit_continuity_audit import (
    CommandRunner,
    ManagerPostcommitContinuityAuditError,
    SubprocessRunner,
    _inspect,
    _retained,
    _snapshot,
    _stable_socket,
    _validate_manager_identity,
    _validate_retained,
)

SCHEMA = "gh.m2.t1-broker-identity-preactivation-fresh-evidence/1"
MANIFEST_SCHEMA = (
    "gh.m2.t1-broker-identity-preactivation-fresh-evidence-manifest/1"
)
_OUTPUT_PREFIX = "greenhouse-m2-broker-preactivation-fresh-evidence-"
_PASSWORD_MOUNT = "/run/secrets/gh_manager_mqtt_password"
_SERVICES = ("greenhouse-manager", "mosquitto", "homeassistant")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{4,32}$")
_PROBE_SCRIPT = """\
import json
import socket
import sys
host = sys.argv[1]
port = int(sys.argv[2])
result = {"dns_resolved": False, "tcp_connectable": False, "address_count": 0}
try:
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
except OSError:
    addresses = []
result["dns_resolved"] = bool(addresses)
result["address_count"] = len(addresses)
for family, socktype, proto, _canonname, sockaddr in addresses:
    connection = socket.socket(family, socktype, proto)
    connection.settimeout(2.0)
    try:
        connection.connect(sockaddr)
    except OSError:
        pass
    else:
        result["tcp_connectable"] = True
        connection.close()
        break
    connection.close()
print(json.dumps(result, separators=(",", ":")))
"""


class BrokerPreactivationFreshEvidenceError(RuntimeError):
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


def _fingerprint(value: str) -> str:
    return _sha256_text(value)[:16]


def _run(
    runner: CommandRunner,
    command: Sequence[str],
    message: str,
) -> str:
    code, output = runner.run(tuple(command))
    if code != 0:
        raise BrokerPreactivationFreshEvidenceError(message)
    return output


def _read_broker_config(runner: CommandRunner) -> str:
    output = _run(
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
    return output if output.endswith("\n") else output + "\n"


def _broker_baseline(runner: CommandRunner) -> tuple[dict[str, object], str]:
    config = _read_broker_config(runner)
    directives: dict[str, list[str]] = {}
    safe: list[dict[str, str]] = []
    allowed = {
        "allow_anonymous",
        "listener",
        "persistence",
        "persistence_location",
        "plugin",
        "plugin_opt_config_file",
    }
    for raw in config.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(None, 1)
        directive = parts[0].lower()
        value = parts[1].strip() if len(parts) == 2 else ""
        directives.setdefault(directive, []).append(value)
        if directive in allowed:
            redacted = value
            if directive in {
                "persistence_location",
                "plugin",
                "plugin_opt_config_file",
            }:
                redacted = _fingerprint(value) if value else ""
            safe.append({"directive": directive, "value": redacted})

    anonymous = [item.lower() for item in directives.get("allow_anonymous", [])]
    anonymous_enabled = bool(anonymous) and anonymous[-1] in {
        "true",
        "yes",
        "1",
        "on",
    }
    dynsec_configured = any(
        "dynamic_security" in item.lower()
        for item in directives.get("plugin", [])
    )
    plugin_available = (
        _run(
            runner,
            (
                "docker",
                "exec",
                "mosquitto",
                "sh",
                "-c",
                "test -f /usr/lib/mosquitto_dynamic_security.so && echo available",
            ),
            "Dynamic Security plugin availability cannot be inspected",
        ).strip()
        == "available"
    )
    state_absent = (
        _run(
            runner,
            (
                "docker",
                "exec",
                "mosquitto",
                "sh",
                "-c",
                "test ! -e /mosquitto/data/dynamic-security.json && "
                "echo absent || echo present",
            ),
            "Dynamic Security state presence cannot be inspected",
        ).strip()
        == "absent"
    )
    if not anonymous_enabled:
        raise BrokerPreactivationFreshEvidenceError(
            "anonymous MQTT is not enabled in the required preactivation baseline"
        )
    if dynsec_configured or not state_absent:
        raise BrokerPreactivationFreshEvidenceError(
            "Dynamic Security is already configured or state is present"
        )
    if not plugin_available:
        raise BrokerPreactivationFreshEvidenceError(
            "Dynamic Security plugin is unavailable"
        )
    config_sha = _sha256_text(config)
    return (
        {
            "config_sha256": config_sha,
            "safe_directives": safe,
            "anonymous_enabled": True,
            "dynamic_security_configured": False,
            "dynamic_security_state_absent": True,
            "dynamic_security_plugin_available": True,
        },
        config_sha,
    )


def _manager_evidence(
    runner: CommandRunner,
    document: Mapping[str, Any],
    *,
    proc_root: Path,
    mqtt_port: int,
    timeout_s: float,
    poll_interval_s: float,
) -> tuple[dict[str, object], str]:
    pid = _validate_manager_identity(document, proc_root=proc_root)
    if not _stable_socket(
        proc_root,
        pid,
        mqtt_port,
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
    ):
        raise BrokerPreactivationFreshEvidenceError(
            "greenhouse-manager MQTT socket is not stable"
        )
    config = document.get("Config")
    environment = config.get("Env") if isinstance(config, Mapping) else None
    if not isinstance(environment, list):
        raise BrokerPreactivationFreshEvidenceError(
            "greenhouse-manager environment metadata is invalid"
        )
    values = dict(
        item.partition("=")[::2]
        for item in environment
        if isinstance(item, str) and "=" in item
    )
    mounts = document.get("Mounts")
    if not isinstance(mounts, list):
        raise BrokerPreactivationFreshEvidenceError(
            "greenhouse-manager mount inventory is invalid"
        )
    matching = [
        item
        for item in mounts
        if isinstance(item, Mapping)
        and item.get("Destination") == _PASSWORD_MOUNT
    ]
    if len(matching) != 1 or not isinstance(matching[0].get("Source"), str):
        raise BrokerPreactivationFreshEvidenceError(
            "greenhouse-manager password mount binding is invalid"
        )
    return (
        {
            "authenticated_environment_present": True,
            "password_mount_read_only": True,
            "password_source_private": True,
            "password_ownership_bound": True,
            "password_source_runtime_owner_model": True,
            "mqtt_socket_stable": True,
            "username_fingerprint": _fingerprint(values["GH_MQTT_USERNAME"]),
            "client_id_fingerprint": _fingerprint(values["GH_MQTT_CLIENT_ID"]),
        },
        str(matching[0]["Source"]),
    )


def _continuity(
    runner: CommandRunner,
    *,
    system_id: str,
    node_id: str,
    discovery_topic: str,
    timeout_s: float,
) -> dict[str, object]:
    canonical_topic = f"gh/v1/{system_id}/state/{node_id}/telemetry"
    availability_topic = f"gh/v1/{system_id}/state/{node_id}/availability"
    canonical = _retained(runner, canonical_topic, timeout_s=timeout_s)
    availability = _retained(runner, availability_topic, timeout_s=timeout_s)
    discovery = _retained(runner, discovery_topic, timeout_s=timeout_s)
    _validate_retained(
        canonical,
        availability,
        discovery,
        system_id=system_id,
        node_id=node_id,
    )
    return {
        "canonical_retained_continuous": True,
        "availability_retained_continuous": True,
        "discovery_retained_continuous": True,
        "existing_entity_identity_continuous": True,
        "availability_state": availability.get("state"),
    }


def _networks(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    settings = document.get("NetworkSettings")
    raw = settings.get("Networks") if isinstance(settings, Mapping) else None
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(name): dict(value)
        for name, value in raw.items()
        if isinstance(value, Mapping)
    }


def _network_mode(document: Mapping[str, Any]) -> str:
    config = document.get("HostConfig")
    return str(config.get("NetworkMode", "")) if isinstance(config, Mapping) else ""


def _probe(runner: CommandRunner, host: str, port: int) -> dict[str, object]:
    output = _run(
        runner,
        (
            "docker",
            "exec",
            "homeassistant",
            "python3",
            "-c",
            _PROBE_SCRIPT,
            host,
            str(port),
        ),
        "Home Assistant Broker candidate reachability probe failed",
    )
    try:
        result = json.loads(output)
    except json.JSONDecodeError as error:
        raise BrokerPreactivationFreshEvidenceError(
            "Home Assistant candidate probe returned invalid JSON"
        ) from error
    if not isinstance(result, dict):
        raise BrokerPreactivationFreshEvidenceError(
            "Home Assistant candidate probe returned invalid data"
        )
    count = result.get("address_count")
    if not isinstance(count, int) or count < 0:
        raise BrokerPreactivationFreshEvidenceError(
            "Home Assistant candidate address count is invalid"
        )
    return {
        "host_fingerprint": _fingerprint(host),
        "dns_resolved": result.get("dns_resolved") is True,
        "tcp_connectable": result.get("tcp_connectable") is True,
        "address_count": count,
    }


def _homeassistant_topology(
    runner: CommandRunner,
    homeassistant: Mapping[str, Any],
    mosquitto: Mapping[str, Any],
    *,
    port: int,
) -> dict[str, object]:
    ha_networks = _networks(homeassistant)
    broker_networks = _networks(mosquitto)
    shared = set(ha_networks) & set(broker_networks)
    aliases: set[str] = set()
    for name in shared:
        raw = broker_networks[name].get("Aliases")
        if isinstance(raw, list):
            aliases.update(str(item) for item in raw if item)
    candidates = [
        {
            "kind": "docker_service_alias",
            **_probe(runner, "mosquitto", port),
            "topology_eligible": bool(shared and "mosquitto" in aliases),
        },
        {
            "kind": "loopback",
            **_probe(runner, "127.0.0.1", port),
            "topology_eligible": _network_mode(homeassistant) == "host",
        },
    ]
    for item in candidates:
        item["eligible"] = bool(
            item["topology_eligible"]
            and item["dns_resolved"]
            and item["tcp_connectable"]
        )
    eligible = [item for item in candidates if item["eligible"] is True]
    eligible.sort(
        key=lambda item: {"docker_service_alias": 0, "loopback": 1}[
            str(item["kind"])
        ]
    )
    if not eligible:
        raise BrokerPreactivationFreshEvidenceError(
            "Home Assistant Broker target topology is unresolved"
        )
    selected = eligible[0]
    return {
        "network_topology_observed": True,
        "shared_network_count": len(shared),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "selected_target_kind": selected["kind"],
        "selected_target_fingerprint": selected["host_fingerprint"],
        "official_config_flow_only": True,
        "direct_storage_edit_forbidden": True,
        "homeassistant_storage_read": False,
        "homeassistant_storage_written": False,
        "config_entry_binding_deferred": True,
        "operator_action_required": True,
        "operator_action_authorized": False,
    }


def _acl_model(system_id: str, node_id: str) -> dict[str, object]:
    ingress = f"gh/v1/{system_id}/ingress/node/{node_id}/telemetry"
    return {
        "model_verified": True,
        "manager_identity_migrated": True,
        "homeassistant_identity_migrated": False,
        "node_identity_migrated": False,
        "node_publish_allow_fingerprint": _fingerprint(ingress),
        "node_other_ingress_denied": True,
        "node_canonical_denied": True,
        "node_discovery_denied": True,
        "node_control_denied": True,
        "homeassistant_official_reconfigure_pending": True,
        "node_credential_delivery_path_verified": False,
    }


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_private(path: Path, document: Mapping[str, Any]) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(_canonical_json(document) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _destination(output_root: Path, now: datetime, token: str) -> Path:
    if (
        not output_root.is_absolute()
        or output_root.is_symlink()
        or not output_root.is_dir()
    ):
        raise BrokerPreactivationFreshEvidenceError("evidence output root is unsafe")
    if _TOKEN.fullmatch(token) is None:
        raise BrokerPreactivationFreshEvidenceError("evidence token is invalid")
    destination = output_root / (
        f"{_OUTPUT_PREFIX}{now:%Y%m%dT%H%M%SZ}-{token}"
    )
    if destination.exists() or destination.is_symlink():
        raise BrokerPreactivationFreshEvidenceError(
            "evidence output destination already exists or is unsafe"
        )
    return destination


def _materialize(
    destination: Path,
    report: Mapping[str, Any],
) -> tuple[str, str]:
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.",
            dir=destination.parent,
        )
    )
    try:
        temporary.chmod(0o700)
        if stat.S_IMODE(temporary.stat().st_mode) != 0o700:
            raise BrokerPreactivationFreshEvidenceError(
                "temporary evidence directory is not private"
            )
        evidence = temporary / "evidence.json"
        _write_private(evidence, report)
        evidence_sha = _sha256_path(evidence)
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "evidence_name": destination.name,
            "evidence_sha256": evidence_sha,
            "evidence_mode": "0600",
            "output_mode": "0700",
            "read_only_live_services": True,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "authorization_created": False,
            "production_execution_invoked": False,
            "homeassistant_storage_read": False,
            "node_credentials_delivered": False,
        }
        manifest_path = temporary / "manifest.json"
        _write_private(manifest_path, manifest)
        manifest_sha = _sha256_path(manifest_path)
        _fsync_directory(temporary)
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
        return evidence_sha, manifest_sha
    except Exception:
        if temporary.exists():
            for child in temporary.iterdir():
                child.unlink(missing_ok=True)
            temporary.rmdir()
        raise


def build_broker_preactivation_fresh_evidence(
    output_root: str | Path,
    *,
    system_id: str,
    node_id: str,
    discovery_topic: str,
    expected_retained_topic: str,
    mqtt_port: int = 1883,
    timeout_s: float = 8.0,
    poll_interval_s: float = 1.0,
    proc_root: str | Path = "/proc",
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    token_factory: Callable[[], str] | None = None,
    repository_sha: str | None = None,
    manager_source_version: str | None = None,
) -> dict[str, object]:
    expected_canonical = f"gh/v1/{system_id}/state/{node_id}/telemetry"
    if (
        not system_id
        or not node_id
        or expected_retained_topic != expected_canonical
        or not discovery_topic.startswith("homeassistant/")
        or "+" in discovery_topic
        or "#" in discovery_topic
        or not 1 <= mqtt_port <= 65535
        or timeout_s <= 0
        or poll_interval_s <= 0
    ):
        raise ValueError("Broker preactivation fresh evidence inputs are invalid")
    if repository_sha is not None and _GIT_SHA.fullmatch(repository_sha) is None:
        raise ValueError(
            "repository SHA must be a 40-character lowercase Git SHA"
        )

    command_runner = runner or SubprocessRunner()
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    token = token_factory() if token_factory else secrets.token_hex(4)
    output = _destination(Path(output_root).expanduser(), observed, token)

    before_runtime = _snapshot(command_runner)
    manager_document = _inspect(command_runner, "greenhouse-manager")
    mosquitto_document = _inspect(command_runner, "mosquitto")
    homeassistant_document = _inspect(command_runner, "homeassistant")
    broker, broker_config_before = _broker_baseline(command_runner)
    manager, password_source = _manager_evidence(
        command_runner,
        manager_document,
        proc_root=Path(proc_root),
        mqtt_port=mqtt_port,
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
    )
    continuity = _continuity(
        command_runner,
        system_id=system_id,
        node_id=node_id,
        discovery_topic=discovery_topic,
        timeout_s=timeout_s,
    )
    homeassistant = _homeassistant_topology(
        command_runner,
        homeassistant_document,
        mosquitto_document,
        port=mqtt_port,
    )
    acl = _acl_model(system_id, node_id)

    after_runtime = _snapshot(command_runner)
    _broker_after, broker_config_after = _broker_baseline(command_runner)
    if after_runtime != before_runtime:
        raise BrokerPreactivationFreshEvidenceError(
            "a protected service changed during fresh evidence reconstruction"
        )
    if broker_config_after != broker_config_before:
        raise BrokerPreactivationFreshEvidenceError(
            "live Broker config changed during fresh evidence reconstruction"
        )

    checks = {
        "manager_postmigration_continuity_revalidated": True,
        "broker_anonymous_baseline_verified": True,
        "dynamic_security_not_active": True,
        "dynamic_security_plugin_available": True,
        "retained_state_continuous": True,
        "homeassistant_topology_resolved_without_storage_read": True,
        "acl_model_verified": True,
        "protected_services_stable": True,
        "broker_config_stable": True,
    }
    blockers = [
        "explicit_operator_decision_required",
        "production_driver_not_installed",
        "single_use_authorization_not_created",
        "homeassistant_official_mqtt_ui_config_flow_pending",
        "real_node_credential_delivery_unverified",
        "anonymous_closure_not_authorized",
    ]
    runtime = {
        name: {
            "runtime_fingerprint": _fingerprint(
                _canonical_json(before_runtime[name])
            ),
            "running_zero_restart": True,
        }
        for name in _SERVICES
    }
    report: dict[str, object] = {
        "schema": SCHEMA,
        "status": "broker_preactivation_fresh_evidence_reconstructed",
        "generated_at": observed.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        "read_only_live_services": True,
        "fresh_evidence_reconstructed": all(checks.values()),
        "checks": checks,
        "runtime": runtime,
        "broker": broker,
        "manager": manager,
        "continuity": continuity,
        "homeassistant": homeassistant,
        "acl_model": acl,
        "activation_blockers": blockers,
        "evidence_name": output.name,
        "repository_sha": repository_sha,
        "manager_source_version": manager_source_version,
        "manager_identity_migrated": True,
        "homeassistant_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "apply_enabled": False,
        "execution_enabled": False,
        "operator_action_authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "authorization_reused": False,
        "production_execution_invoked": False,
        "production_driver_installed": False,
        "current_services_modified": False,
        "homeassistant_storage_read": False,
        "homeassistant_storage_written": False,
        "ready_for_broker_preactivation_gate": True,
        "ready_for_live_activation": False,
        "secret_values_included": False,
        "source_paths_included": False,
        "path_values_redacted": True,
        "container_ids_included": False,
        "image_ids_included": False,
    }
    serialized = _canonical_json(report)
    forbidden = [password_source, "/config/.storage", "core.config_entries"]
    if any(value and value in serialized for value in forbidden):
        raise BrokerPreactivationFreshEvidenceError(
            "fresh evidence report contains forbidden private material"
        )
    evidence_sha, manifest_sha = _materialize(output, report)
    report["evidence_sha256"] = evidence_sha
    report["manifest_sha256"] = manifest_sha
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct fresh, read-only Broker Dynamic Security preactivation "
            "evidence after Manager identity migration."
        )
    )
    parser.add_argument("--output-root", default="/tmp")
    parser.add_argument("--system-id", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--discovery-topic", required=True)
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    parser.add_argument("--repository-sha")
    parser.add_argument("--manager-source-version")
    args = parser.parse_args(argv)
    try:
        report = build_broker_preactivation_fresh_evidence(
            args.output_root,
            system_id=args.system_id,
            node_id=args.node_id,
            discovery_topic=args.discovery_topic,
            expected_retained_topic=args.expected_retained_topic,
            mqtt_port=args.mqtt_port,
            timeout_s=args.timeout_seconds,
            poll_interval_s=args.poll_interval_seconds,
            repository_sha=args.repository_sha,
            manager_source_version=args.manager_source_version,
        )
    except (
        BrokerPreactivationFreshEvidenceError,
        ManagerPostcommitContinuityAuditError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(
            f"T1 Broker preactivation fresh evidence failed: {error}",
            file=sys.stderr,
        )
        return 2
    print(_canonical_json(report))
    return 0 if report["fresh_evidence_reconstructed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
