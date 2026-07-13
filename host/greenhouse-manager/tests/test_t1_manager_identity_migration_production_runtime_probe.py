from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import greenhouse_manager.t1_manager_identity_migration_production_runtime_probe as module
from greenhouse_manager.t1_manager_identity_migration_production_host_adapters import (
    ManagerHostBinding,
    ManagerProductionHostTransactionAdapters,
)
from greenhouse_manager.t1_manager_identity_migration_production_integration import (
    ManagerProductionIntegrationError,
    ManagerRuntimeProbeConfiguration,
    build_manager_production_adapters_factory,
    production_integration_capabilities,
)
from greenhouse_manager.t1_manager_identity_migration_production_runtime_probe import (
    ManagerProductionRuntimeProbe,
    ManagerProductionRuntimeProbeError,
)

SYSTEM_ID = "greenhouse"
NODE_ID = "gh-n1-a9f2f8"
DISCOVERY_TOPIC = f"homeassistant/device/{NODE_ID}/config"
CONTAINER_ID = "a" * 64
STARTED_AT = "2026-07-13T08:00:00Z"
PASSWORD_TARGET = "/run/secrets/gh_manager_mqtt_password"


def _write(path: Path, text: str, mode: int = 0o600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)
    return path


def _binding(tmp_path: Path) -> ManagerHostBinding:
    tmp_path.chmod(0o700)
    working = tmp_path / "compose"
    working.mkdir(mode=0o700)
    secret_root = tmp_path / "secrets"
    secret_root.mkdir(mode=0o700)
    password = _write(secret_root / "manager/password", "secret\n")
    material = tmp_path / "material"
    manager_env = _write(
        material / "manager.env",
        "GH_MQTT_USERNAME=gh-manager-user\n"
        f"GH_MQTT_PASSWORD_FILE={PASSWORD_TARGET}\n"
        "GH_MQTT_CLIENT_ID=gh-manager-client\n",
    )
    return ManagerHostBinding(
        project="greenhouse",
        working_dir=working,
        config_files=(_write(working / "compose.yaml", "services: {}\n"),),
        environment_file=_write(working / ".env", "SYSTEM_ID=greenhouse\n"),
        secret_root=secret_root,
        password_target=password,
        auth_environment_target=working / "manager-auth.env",
        overlay_target=working / "docker-compose.manager-auth.yml",
        material_environment=manager_env,
        material_password=_write(material / "password", "secret\n"),
        material_overlay=_write(material / "overlay.yaml", "services: {}\n"),
        username="gh-manager-user",
        client_id="gh-manager-client",
        manager_runtime_uid=os.getuid(),
        manager_runtime_gid=os.getgid(),
        manager_runtime_user_source="container+image+isolated-candidate",
        manager_runtime_image_id="sha256:manager-image-id",
        manager_runtime_user_spec=f"{os.getuid()}:{os.getgid()}",
    )


def _discovery() -> dict[str, object]:
    return {
        "device": {
            "identifiers": [f"gh_{SYSTEM_ID}_{NODE_ID}"],
            "name": "node",
        },
        "components": {
            "temperature": {
                "p": "sensor",
                "unique_id": f"{NODE_ID}_temperature",
            },
            "node_id": {
                "p": "sensor",
                "unique_id": f"{NODE_ID}_node_id",
            },
        },
        "state_topic": f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry",
        "availability": [
            {
                "topic": f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/availability",
                "payload_available": "online",
            }
        ],
    }


def _payloads() -> dict[str, bytes]:
    return {
        f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry": json.dumps(
            {
                "schema": "gh.telemetry/1",
                "node_id": NODE_ID,
                "measurements": {"air_temperature_c": 22.5},
            }
        ).encode(),
        f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/availability": json.dumps(
            {"node_id": NODE_ID, "state": "online"}
        ).encode(),
        DISCOVERY_TOPIC: json.dumps(_discovery()).encode(),
    }


class MappingReader:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads
        self.topics: list[str] = []

    def read(self, topic: str) -> bytes:
        self.topics.append(topic)
        try:
            return self.payloads[topic]
        except KeyError as error:
            raise AssertionError(f"unexpected topic: {topic}") from error


class InspectRunner:
    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        assert command == ("docker", "inspect", "greenhouse-manager")
        return 0, json.dumps([self.document])


def _runtime_fixture(
    tmp_path: Path,
    *,
    include_socket: bool = True,
) -> tuple[ManagerHostBinding, dict[str, Any], Path, Path]:
    binding = _binding(tmp_path)
    log_dir = tmp_path / "docker" / "containers" / CONTAINER_ID
    log_dir.mkdir(parents=True, mode=0o700)
    log_path = log_dir / f"{CONTAINER_ID}-json.log"
    messages = (
        f"Subscribed to gh/v1/{SYSTEM_ID}/ingress/node/+/telemetry",
        f"Subscribed to gh/v1/{SYSTEM_ID}/state/+/telemetry",
        f"Accepted telemetry node={NODE_ID} key=('boot', 1)",
        f"Published Home Assistant discovery node={NODE_ID} topic={DISCOVERY_TOPIC}",
    )
    with log_path.open("w", encoding="utf-8") as stream:
        for index, message in enumerate(messages, start=1):
            stream.write(
                json.dumps(
                    {
                        "time": f"2026-07-13T08:00:0{index}Z",
                        "log": message + "\n",
                    }
                )
                + "\n"
            )
    log_path.chmod(0o600)
    proc_root = tmp_path / "proc"
    tcp = proc_root / "321" / "net" / "tcp"
    tcp.parent.mkdir(parents=True, mode=0o700)
    rows = [
        "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode",
    ]
    if include_socket:
        rows.append(
            "   0: 0100007F:C350 0200007F:075B 01 00000000:00000000 "
            "00:00000000 00000000 0 0 424242"
        )
    tcp.write_text("\n".join(rows) + "\n", encoding="ascii")
    tcp.chmod(0o600)
    document: dict[str, Any] = {
        "Id": CONTAINER_ID,
        "Image": "sha256:manager-image-id",
        "LogPath": str(log_path),
        "RestartCount": 0,
        "State": {
            "Status": "running",
            "Pid": 321,
            "StartedAt": STARTED_AT,
        },
        "Config": {
            "User": f"{os.getuid()}:{os.getgid()}",
            "Env": [
                "GH_MQTT_USERNAME=gh-manager-user",
                "GH_MQTT_CLIENT_ID=gh-manager-client",
                f"GH_MQTT_PASSWORD_FILE={PASSWORD_TARGET}",
                "GH_MQTT_PASSWORD=",
            ]
        },
        "Mounts": [
            {
                "Source": str(binding.password_target),
                "Destination": PASSWORD_TARGET,
                "RW": False,
            }
        ],
    }
    return binding, document, proc_root, log_path


@pytest.fixture(autouse=True)
def _allow_sandbox_runtime_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        module,
        "verify_bound_runtime_identity",
        lambda *_args, **_kwargs: (os.getuid(), os.getgid()),
    )


def _probe(
    tmp_path: Path,
    *,
    payloads: dict[str, bytes] | None = None,
    include_socket: bool = True,
) -> tuple[ManagerProductionRuntimeProbe, MappingReader, InspectRunner, Path]:
    binding, document, proc_root, log_path = _runtime_fixture(
        tmp_path,
        include_socket=include_socket,
    )
    reader = MappingReader(payloads or _payloads())
    runner = InspectRunner(document)
    probe = ManagerProductionRuntimeProbe(
        binding,
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        discovery_topic=DISCOVERY_TOPIC,
        runner=runner,
        reader_factory=lambda: reader,
        proc_root=proc_root,
        timeout_s=0.1,
        poll_interval_s=0.01,
        sleeper=lambda _seconds: None,
    )
    return probe, reader, runner, log_path


def test_passive_runtime_probe_verifies_full_manager_path(tmp_path: Path) -> None:
    probe, reader, runner, _log_path = _probe(tmp_path)

    baseline = probe.capture_baseline()
    probe.verify_authenticated_identity("gh-manager-user", "gh-manager-client")
    probe.verify_ingress_subscription()
    probe.verify_canonical_publication()
    probe.verify_availability_publication()
    probe.verify_discovery_publication()
    probe.verify_reconnect()
    probe.verify_existing_entities()
    probe.verify_legacy_anonymous_path()
    audit = probe.postactivation_audit()

    assert baseline["baseline_captured"] is True
    assert audit["manager_identity_migrated"] is True
    assert audit["rollback_required"] is False
    assert all(audit["checks"].values())
    assert set(runner.commands) == {("docker", "inspect", "greenhouse-manager")}
    assert DISCOVERY_TOPIC in reader.topics


def test_runtime_probe_rejects_unstable_mqtt_session(tmp_path: Path) -> None:
    probe, _reader, _runner, _log_path = _probe(tmp_path, include_socket=False)
    probe.capture_baseline()

    with pytest.raises(
        ManagerProductionRuntimeProbeError,
        match="no stable MQTT TCP session",
    ):
        probe.verify_authenticated_identity("gh-manager-user", "gh-manager-client")


def test_runtime_probe_rejects_password_owner_drift(tmp_path: Path) -> None:
    probe, _reader, _runner, _log_path = _probe(tmp_path)
    probe.binding = replace(
        probe.binding,
        manager_runtime_uid=os.getuid() + 1,
        manager_runtime_user_spec=f"{os.getuid() + 1}:{os.getgid()}",
    )

    with pytest.raises(ManagerProductionRuntimeProbeError, match="password source"):
        probe.verify_authenticated_identity("gh-manager-user", "gh-manager-client")


def test_runtime_probe_rejects_changed_discovery_identity(tmp_path: Path) -> None:
    payloads = _payloads()
    probe, reader, _runner, _log_path = _probe(tmp_path, payloads=payloads)
    probe.capture_baseline()
    changed = _discovery()
    changed["device"] = {"identifiers": ["changed"], "name": "node"}
    reader.payloads[DISCOVERY_TOPIC] = json.dumps(changed).encode()

    with pytest.raises(
        ManagerProductionRuntimeProbeError,
        match="identity changed",
    ):
        probe.verify_discovery_publication()


def test_runtime_probe_rejects_log_path_not_bound_to_container(tmp_path: Path) -> None:
    probe, _reader, runner, log_path = _probe(tmp_path)
    runner.document["LogPath"] = str(log_path.with_name("other-json.log"))

    with pytest.raises(
        ManagerProductionRuntimeProbeError,
        match="log path is unsafe",
    ):
        probe.verify_authenticated_identity("gh-manager-user", "gh-manager-client")


class BaselineProbe:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.captured = False

    def capture_baseline(self) -> dict[str, object]:
        self.captured = True
        return {"baseline_captured": True}


def test_integration_factory_uses_dedicated_empty_host_workspace(tmp_path: Path) -> None:
    binding = _binding(tmp_path)
    transaction_workspace = tmp_path / "transaction"
    transaction_workspace.mkdir(mode=0o700)
    _write(transaction_workspace / "journal.json", "{}\n")
    driver = _write(tmp_path / "driver.json", "{}\n")
    execution = tmp_path / "execution"
    execution.mkdir(mode=0o700)
    preparation = tmp_path / "preparation"
    preparation.mkdir(mode=0o700)
    probes: list[BaselineProbe] = []

    def probe_factory(*_args: object, **_kwargs: object) -> BaselineProbe:
        probe = BaselineProbe()
        probes.append(probe)
        return probe

    factory = build_manager_production_adapters_factory(
        ManagerRuntimeProbeConfiguration(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
        ),
        binding_loader=lambda *_args, **_kwargs: (binding, {}, {}),
        probe_factory=probe_factory,
    )

    adapters = factory(
        driver,
        execution,
        preparation,
        transaction_workspace,
        runner=InspectRunner({}),
    )

    assert isinstance(adapters, ManagerProductionHostTransactionAdapters)
    assert probes and probes[0].captured is True
    host_workspace = transaction_workspace / "host-adapters"
    assert host_workspace.is_dir()
    assert host_workspace.stat().st_mode & 0o777 == 0o700
    assert list(host_workspace.iterdir()) == []
    assert (transaction_workspace / "journal.json").is_file()


def test_integration_factory_rejects_reused_host_workspace(tmp_path: Path) -> None:
    binding = _binding(tmp_path)
    transaction_workspace = tmp_path / "transaction"
    transaction_workspace.mkdir(mode=0o700)
    (transaction_workspace / "host-adapters").mkdir(mode=0o700)
    driver = _write(tmp_path / "driver.json", "{}\n")
    execution = tmp_path / "execution"
    execution.mkdir(mode=0o700)
    preparation = tmp_path / "preparation"
    preparation.mkdir(mode=0o700)
    factory = build_manager_production_adapters_factory(
        ManagerRuntimeProbeConfiguration(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
        ),
        binding_loader=lambda *_args, **_kwargs: (binding, {}, {}),
        probe_factory=BaselineProbe,
    )

    with pytest.raises(ManagerProductionIntegrationError, match="already exists"):
        factory(
            driver,
            execution,
            preparation,
            transaction_workspace,
            runner=InspectRunner({}),
        )


def test_production_integration_capabilities_remain_non_executable() -> None:
    report = production_integration_capabilities()

    assert report["production_runtime_probe_implemented"] is True
    assert report["orchestrator_integration_factory_implemented"] is True
    assert report["execution_entrypoint_installed"] is False
    assert report["production_executor_available"] is False
    assert report["execution_enabled"] is False
    assert report["apply_enabled"] is False
    assert report["current_services_modified"] is False
    assert report["preserve_anonymous"] is True
