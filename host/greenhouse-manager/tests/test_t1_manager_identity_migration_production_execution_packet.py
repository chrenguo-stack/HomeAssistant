from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

import greenhouse_manager.t1_manager_identity_migration_production_execution_packet as module
from greenhouse_manager.t1_manager_identity_migration_production_execution_packet import (
    GuardedRuntimeProbe,
    ManagerProductionExecutionPacketError,
    execute_manager_identity_production_packet,
    main,
)

MANAGER = "greenhouse-manager"
MOSQUITTO = "mosquitto"
HOMEASSISTANT = "homeassistant"
IMAGE_MANAGER = "sha256:" + "1" * 64
IMAGE_MOSQUITTO = "sha256:" + "2" * 64
IMAGE_HOMEASSISTANT = "sha256:" + "3" * 64
CONFIRMATION = (
    "EXECUTE-M2-MANAGER-MIGRATION:0123456789abcdef01234567:"
    "aaaaaaaaaaaaaaaa:bbbbbbbbbbbbbbbb:cccccccccccccccc"
)


def _container(
    name: str,
    container_id: str,
    image_id: str,
    *,
    started_at: str,
    restarts: int = 0,
) -> dict[str, object]:
    return {
        "Name": f"/{name}",
        "Id": container_id,
        "Image": image_id,
        "RestartCount": restarts,
        "State": {"Status": "running", "StartedAt": started_at},
        "Config": {},
    }


def _baseline() -> dict[str, dict[str, object]]:
    return {
        MANAGER: _container(
            MANAGER,
            "a" * 64,
            IMAGE_MANAGER,
            started_at="2026-07-13T08:00:00Z",
        ),
        MOSQUITTO: _container(
            MOSQUITTO,
            "b" * 64,
            IMAGE_MOSQUITTO,
            started_at="2026-07-12T08:00:00Z",
        ),
        HOMEASSISTANT: _container(
            HOMEASSISTANT,
            "c" * 64,
            IMAGE_HOMEASSISTANT,
            started_at="2026-07-12T09:00:00Z",
        ),
    }


def _after() -> dict[str, dict[str, object]]:
    result = _baseline()
    result[MANAGER] = _container(
        MANAGER,
        "d" * 64,
        IMAGE_MANAGER,
        started_at="2026-07-13T08:10:00Z",
    )
    return result


class SequenceInspectRunner:
    def __init__(self, snapshots: list[dict[str, dict[str, object]]]) -> None:
        self.snapshots = snapshots
        self.calls: defaultdict[str, int] = defaultdict(int)
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        assert command[:2] == ("docker", "inspect")
        name = command[2]
        index = self.calls[name]
        self.calls[name] += 1
        snapshot_index = min(index, len(self.snapshots) - 1)
        return 0, json.dumps([self.snapshots[snapshot_index][name]])


def _transaction() -> dict[str, object]:
    return {
        "transaction_id": "manager_transaction_0123456789",
        "authorization_id": "0123456789abcdef01234567",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "mutation_completed": True,
        "postactivation_verified": True,
        "rollback_completed": False,
        "manager_identity_migrated": True,
        "node_credentials_delivered": False,
        "current_services_modified": True,
        "mosquitto_modified": False,
        "homeassistant_modified": False,
        "nodes_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def _execute(
    tmp_path: Path,
    runner: SequenceInspectRunner,
    *,
    target: str = MANAGER,
    execute_enabled: bool = True,
    production_enabled: bool = True,
    confirmation: str = CONFIRMATION,
    orchestrator: Any = None,
) -> dict[str, object]:
    active_orchestrator = orchestrator or (lambda *_args, **_kwargs: _transaction())
    return execute_manager_identity_production_packet(
        tmp_path / "authorization.json",
        tmp_path / "execution-preparation",
        tmp_path / "driver.json",
        tmp_path / "preparation",
        tmp_path / "greenhouse-m2-manager-production-transactions.test",
        system_id="greenhouse",
        node_id="gh-n1-a9f2f8",
        discovery_topic="homeassistant/device/gh-n1-a9f2f8/config",
        execution_confirmation=confirmation,
        target=target,
        execute_manager_migration=execute_enabled,
        enable_production_execution=production_enabled,
        runner=runner,
        orchestrator=active_orchestrator,
    )


@pytest.mark.parametrize(
    ("execute_enabled", "production_enabled"),
    [(False, False), (True, False), (False, True)],
)
def test_packet_requires_both_enable_flags_before_inspect(
    tmp_path: Path,
    execute_enabled: bool,
    production_enabled: bool,
) -> None:
    runner = SequenceInspectRunner([_baseline()])

    with pytest.raises(
        ManagerProductionExecutionPacketError,
        match="both production execution enable flags are required",
    ):
        _execute(
            tmp_path,
            runner,
            execute_enabled=execute_enabled,
            production_enabled=production_enabled,
        )

    assert runner.commands == []


@pytest.mark.parametrize(
    ("target", "confirmation", "message"),
    [
        (MOSQUITTO, CONFIRMATION, "target must be greenhouse-manager"),
        (MANAGER, "wrong", "exact second manager migration confirmation is required"),
    ],
)
def test_packet_rejects_target_or_confirmation_before_inspect(
    tmp_path: Path,
    target: str,
    confirmation: str,
    message: str,
) -> None:
    runner = SequenceInspectRunner([_baseline()])

    with pytest.raises(ManagerProductionExecutionPacketError, match=message):
        _execute(tmp_path, runner, target=target, confirmation=confirmation)

    assert runner.commands == []


def test_success_changes_only_manager_container_identity(tmp_path: Path) -> None:
    runner = SequenceInspectRunner([_baseline(), _after()])
    observed: dict[str, object] = {}

    def orchestrator(*_args: object, **kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        return _transaction()

    report = _execute(tmp_path, runner, orchestrator=orchestrator)
    encoded = json.dumps(report)

    assert observed["execution_enabled"] is True
    assert callable(observed["adapters_factory"])
    assert report["production_execution_completed"] is True
    assert report["greenhouse_manager_recreated"] is True
    assert report["greenhouse_manager_image_preserved"] is True
    assert report["mosquitto_unchanged"] is True
    assert report["homeassistant_unchanged"] is True
    assert report["node_credentials_delivered"] is False
    assert report["preserve_anonymous"] is True
    assert report["secret_values_included"] is False
    assert report["path_values_redacted"] is True
    assert "a" * 64 not in encoded
    assert "d" * 64 not in encoded
    assert "sha256:" not in encoded


def test_protected_service_drift_rejects_success(tmp_path: Path) -> None:
    changed = _after()
    changed[MOSQUITTO] = _container(
        MOSQUITTO,
        "e" * 64,
        IMAGE_MOSQUITTO,
        started_at="2026-07-13T08:11:00Z",
    )
    runner = SequenceInspectRunner([_baseline(), changed])

    with pytest.raises(
        ManagerProductionExecutionPacketError,
        match="protected service changed",
    ):
        _execute(tmp_path, runner)


def test_manager_image_drift_or_missing_recreate_is_rejected(tmp_path: Path) -> None:
    image_changed = _after()
    image_changed[MANAGER] = _container(
        MANAGER,
        "d" * 64,
        "sha256:" + "9" * 64,
        started_at="2026-07-13T08:10:00Z",
    )
    with pytest.raises(ManagerProductionExecutionPacketError, match="image changed"):
        _execute(tmp_path, SequenceInspectRunner([_baseline(), image_changed]))

    with pytest.raises(ManagerProductionExecutionPacketError, match="was not recreated"):
        _execute(tmp_path, SequenceInspectRunner([_baseline(), _baseline()]))


def test_orchestrator_failure_checks_protected_services_and_reraises(
    tmp_path: Path,
) -> None:
    runner = SequenceInspectRunner([_baseline(), _baseline()])

    def failing_orchestrator(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("injected orchestrator failure")

    with pytest.raises(RuntimeError, match="injected orchestrator failure"):
        _execute(tmp_path, runner, orchestrator=failing_orchestrator)

    assert runner.calls[MOSQUITTO] == 2
    assert runner.calls[HOMEASSISTANT] == 2


class FakeInnerProbe:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def capture_baseline(self) -> dict[str, object]:
        self.calls.append("baseline")
        return {"baseline_captured": True}

    def verify_authenticated_identity(self, _username: str, _client_id: str) -> None:
        self.calls.append("identity")

    def verify_ingress_subscription(self) -> None:
        self.calls.append("ingress")

    def verify_canonical_publication(self) -> None:
        self.calls.append("canonical")

    def verify_availability_publication(self) -> None:
        self.calls.append("availability")

    def verify_discovery_publication(self) -> None:
        self.calls.append("discovery")

    def verify_reconnect(self) -> None:
        self.calls.append("reconnect")

    def verify_existing_entities(self) -> None:
        self.calls.append("entities")

    def verify_legacy_anonymous_path(self) -> None:
        self.calls.append("legacy")

    def postactivation_audit(self) -> dict[str, object]:
        self.calls.append("audit")
        return {"checks": {"inner": True}, "manager_identity_migrated": True}


class FakeGuard:
    def __init__(self) -> None:
        self.recreated_checks = 0
        self.protected_checks = 0

    def verify_manager_recreated_and_protected_unchanged(self) -> None:
        self.recreated_checks += 1

    def verify_protected_services_unchanged(self) -> None:
        self.protected_checks += 1


def test_guarded_probe_injects_protected_service_checks() -> None:
    inner = FakeInnerProbe()
    guard = FakeGuard()
    probe = GuardedRuntimeProbe(inner, guard)  # type: ignore[arg-type]

    probe.verify_existing_entities()
    probe.verify_legacy_anonymous_path()
    report = probe.postactivation_audit()

    assert inner.calls == ["entities", "legacy", "audit"]
    assert guard.recreated_checks == 2
    assert guard.protected_checks == 1
    assert report["protected_services_unchanged"] is True
    assert all(report["checks"].values())


def test_cli_emits_path_redacted_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    captured: dict[str, object] = {}

    def fake_execute(*_args: object, **kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "schema": module.SCHEMA,
            "production_execution_completed": True,
            "secret_values_included": False,
            "path_values_redacted": True,
        }

    monkeypatch.setattr(module, "execute_manager_identity_production_packet", fake_execute)
    rc = main(
        [
            "/private/auth.json",
            "/private/execution",
            "/private/driver.json",
            "/private/preparation",
            "/private/transactions",
            "--system-id",
            "greenhouse",
            "--node-id",
            "gh-n1-a9f2f8",
            "--discovery-topic",
            "homeassistant/device/gh-n1-a9f2f8/config",
            "--execution-confirmation",
            CONFIRMATION,
            "--target",
            MANAGER,
            "--execute-manager-migration",
            "--enable-production-execution",
        ]
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert captured["target"] == MANAGER
    assert captured["execute_manager_migration"] is True
    assert captured["enable_production_execution"] is True
    assert "password" not in output.lower()
    assert "client_id" not in output.lower()
    assert "/private/" not in output
    assert json.loads(output)["production_execution_completed"] is True
