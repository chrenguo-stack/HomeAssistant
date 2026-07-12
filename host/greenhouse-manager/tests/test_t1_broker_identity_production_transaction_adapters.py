from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_broker_identity_production_transaction_adapters import (
    BrokerIdentityProductionTransactionAdaptersError,
    ProductionTransactionAdapters,
)
from greenhouse_manager.t1_shadow import (
    PLUGIN_CONFIG_LINE,
    PLUGIN_LINE,
    PLUGIN_PASSWORD_INIT_LINE,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
PLAN_SHA = "1" * 64
CONTRACT_SHA = "2" * 64
MANIFEST_SHA = "3" * 64
ADAPTER_SHA = "4" * 64


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_private(path: Path, value: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_bytes(value)
    path.chmod(0o600)
    return path


def _write_json(path: Path, value: dict[str, object]) -> Path:
    return _write_private(path, json.dumps(value, sort_keys=True))


class FakeDriver:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_request = False

    def restart_mosquitto(self) -> None:
        self.calls.append("restart")

    def wait_for_dynamic_security_state(self, state_file: Path) -> None:
        self.calls.append("wait")
        state_file.write_text("{}\n", encoding="utf-8")

    def apply_exact_request(
        self,
        commands: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        bootstrap_config: str,
    ) -> None:
        self.calls.append("request")
        assert commands
        assert "-u admin" in bootstrap_config
        if self.fail_request:
            raise RuntimeError("injected request failure")

    def verify_provisioning_identity(self, provisioning_config: str) -> None:
        self.calls.append("verify-provisioning")
        assert "-u provisioning" in provisioning_config

    def delete_bootstrap_admin(self, provisioning_config: str) -> None:
        self.calls.append("delete-bootstrap")
        assert "-u provisioning" in provisioning_config

    def verify_bootstrap_rejected(self, bootstrap_config: str) -> None:
        self.calls.append("verify-bootstrap-rejected")
        assert "-u admin" in bootstrap_config

    def postactivation_audit(
        self,
        *,
        expected_retained_topic: str,
        homeassistant_update: dict[str, Any],
        provisioning_config: str,
        bootstrap_config: str,
    ) -> dict[str, object]:
        self.calls.append("audit")
        assert expected_retained_topic == TOPIC
        assert homeassistant_update["username"] == "homeassistant"
        assert "-u provisioning" in provisioning_config
        assert "-u admin" in bootstrap_config
        return {
            "checks": {"all": True},
            "activation_verified": True,
            "rollback_required": False,
            "broker_identity_activated": True,
            "ready_for_homeassistant_reconfigure_handoff": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }

    def restart_after_rollback(self) -> None:
        self.calls.append("rollback-restart")

    def verify_anonymous_retained_state(self, topic: str) -> None:
        self.calls.append("verify-anonymous")
        assert topic == TOPIC


def _fixture(tmp_path: Path) -> dict[str, object]:
    deployment = tmp_path / "deployment"
    config = deployment / "mosquitto/config"
    data = deployment / "mosquitto/data"
    config.mkdir(parents=True, mode=0o700)
    data.mkdir(parents=True, mode=0o700)
    config_file = config / "mosquitto.conf"
    config_file.write_text(
        "persistence true\nallow_anonymous true\nlistener 1883 0.0.0.0\n",
        encoding="utf-8",
    )
    config_file.chmod(0o600)
    retained = data / "mosquitto.db"
    retained.write_bytes(b"baseline-retained")
    retained.chmod(0o600)
    state = data / "dynamic-security.json"

    handoff = tmp_path / "handoff"
    material = {
        "material/broker/dynsec-request.json": json.dumps(
            {"commands": [{"command": "setDefaultACLAccess", "acls": []}]}
        ),
        "material/broker/mosquitto-plugin.conf": (
            f"{PLUGIN_LINE}\n{PLUGIN_CONFIG_LINE}\n{PLUGIN_PASSWORD_INIT_LINE}\n"
        ),
        "material/bootstrap/dynsec-password-init": "bootstrap-password\n",
        "material/bootstrap/admin-client.conf": (
            "-h 127.0.0.1\n-u admin\n-P bootstrap-password\n-i admin-client\n-V 5\n"
        ),
        "material/provisioning/mosquitto-client.conf": (
            "-h 127.0.0.1\n-u provisioning\n-P provisioning-password\n-i provisioning-client\n-V 5\n"
        ),
        "material/homeassistant/mqtt-update.json": json.dumps(
            {
                "username": "homeassistant",
                "password": "ha-password",
                "required_client_id": "homeassistant-client",
            }
        ),
    }
    bindings: list[dict[str, object]] = []
    for relative, content in material.items():
        path = _write_private(handoff / relative, content)
        bindings.append(
            {
                "path": relative,
                "sha256": _sha(path),
                "contains_secret": "password" in relative
                or relative.endswith("client.conf")
                or relative.endswith("mqtt-update.json"),
            }
        )

    adapter = {
        "schema": "gh.m2.t1-broker-identity-production-transaction-adapter-contract/1",
        "adapter_contract_sha256": ADAPTER_SHA,
        "transaction_plan_sha256": PLAN_SHA,
        "contract_sha256": CONTRACT_SHA,
        "runtime_binding_manifest_sha256": MANIFEST_SHA,
    }
    plan = {
        "schema": "gh.m2.t1-broker-identity-activation-readiness-transaction-plan/1",
        "plan_sha256": PLAN_SHA,
    }
    executor = {
        "schema": "gh.m2.t1-broker-identity-production-executor-contract/1",
        "contract_sha256": CONTRACT_SHA,
        "handoff": handoff.name,
        "material_bindings": bindings,
    }
    manifest = {
        "schema": "gh.m2.t1-broker-identity-runtime-binding-manifest/1",
        "manifest_sha256": MANIFEST_SHA,
        "baseline_config_sha256": _sha(config_file),
        "paths": {
            "config_source": str(config.resolve()),
            "data_source": str(data.resolve()),
            "config_file": str(config_file.resolve()),
            "dynamic_security_state_file": str(state.resolve()),
        },
    }
    inputs = tmp_path / "inputs"
    driver = FakeDriver()
    return {
        "adapter": _write_json(inputs / "adapter.json", adapter),
        "plan": _write_json(inputs / "plan.json", plan),
        "executor": _write_json(inputs / "executor.json", executor),
        "manifest": _write_json(inputs / "manifest.json", manifest),
        "handoff": handoff,
        "workspace": tmp_path / "greenhouse-m2-production-transaction-test",
        "config": config,
        "data": data,
        "config_file": config_file,
        "retained": retained,
        "state": state,
        "baseline_config": config_file.read_bytes(),
        "baseline_retained": retained.read_bytes(),
        "driver": driver,
    }


def _adapters(fixture: dict[str, object]) -> ProductionTransactionAdapters:
    return ProductionTransactionAdapters(
        fixture["adapter"],
        fixture["plan"],
        fixture["executor"],
        fixture["manifest"],
        fixture["handoff"],
        fixture["workspace"],
        expected_retained_topic=TOPIC,
        driver=fixture["driver"],
        adapter_contract_verifier=lambda _document: {
            "verified": True,
            "adapter_contract_sha256": ADAPTER_SHA,
        },
        plan_verifier=lambda _document: {
            "verified": True,
            "plan_sha256": PLAN_SHA,
        },
        executor_verifier=lambda _document: {
            "verified": True,
            "contract_sha256": CONTRACT_SHA,
        },
        manifest_verifier=lambda _path: {
            "verified": True,
            "manifest_sha256": MANIFEST_SHA,
        },
    )


def test_prepares_private_snapshot_without_mutating_live_paths(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    adapters = _adapters(fixture)
    report = adapters.prepare()

    assert report["production_transaction_adapters_installed"] is True
    assert report["execution_entrypoint_installed"] is False
    assert report["execution_enabled"] is False
    assert report["current_services_modified"] is False
    assert fixture["config_file"].read_bytes() == fixture["baseline_config"]
    assert fixture["retained"].read_bytes() == fixture["baseline_retained"]
    workspace = fixture["workspace"]
    assert workspace.stat().st_mode & 0o777 == 0o700
    assert (workspace / "snapshot-inventory.json").stat().st_mode & 0o777 == 0o600


def test_mutates_a_bound_replica_and_restores_complete_snapshot(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    adapters = _adapters(fixture)
    mutation = adapters.mutation_executor()
    audit = adapters.postactivation_auditor()

    assert mutation["mosquitto_restarted"] is True
    assert mutation["bootstrap_admin_removed"] is True
    assert audit["activation_verified"] is True
    text = fixture["config_file"].read_text(encoding="utf-8")
    assert PLUGIN_LINE in text
    assert fixture["state"].is_file()
    assert not (fixture["config"] / "dynsec-password-init").exists()

    extra = fixture["data"] / "created-after-snapshot.bin"
    extra.write_bytes(b"extra")
    rollback = adapters.rollback_executor()

    assert rollback["rollback_completed"] is True
    assert fixture["config_file"].read_bytes() == fixture["baseline_config"]
    assert fixture["retained"].read_bytes() == fixture["baseline_retained"]
    assert not fixture["state"].exists()
    assert not extra.exists()
    assert fixture["driver"].calls == [
        "restart",
        "wait",
        "request",
        "verify-provisioning",
        "delete-bootstrap",
        "verify-bootstrap-rejected",
        "verify-provisioning",
        "audit",
        "rollback-restart",
        "verify-anonymous",
    ]


def test_request_failure_can_be_followed_by_verified_rollback(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["driver"].fail_request = True
    adapters = _adapters(fixture)

    with pytest.raises(RuntimeError, match="injected request failure"):
        adapters.mutation_executor()
    assert adapters.mutation_started is True

    rollback = adapters.rollback_executor()
    assert rollback["rollback_completed"] is True
    assert fixture["config_file"].read_bytes() == fixture["baseline_config"]
    assert not fixture["state"].exists()


def test_rejects_live_config_drift_before_snapshot(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["config_file"].write_text("changed\n", encoding="utf-8")

    with pytest.raises(
        BrokerIdentityProductionTransactionAdaptersError,
        match="baseline configuration has drifted",
    ):
        _adapters(fixture).prepare()


def test_rejects_symlink_in_live_tree(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    (fixture["config"] / "unsafe-link").symlink_to(fixture["config_file"])

    with pytest.raises(
        BrokerIdentityProductionTransactionAdaptersError,
        match="snapshot source contains a symlink",
    ):
        _adapters(fixture).prepare()


def test_snapshot_copy_retries_until_source_inventory_is_stable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from greenhouse_manager import (
        t1_broker_identity_production_transaction_adapters as adapter_module,
    )

    source = tmp_path / "source"
    source.mkdir()
    value = source / "value.bin"
    value.write_bytes(b"first")
    destination = tmp_path / "snapshot"
    original = adapter_module._record_tree
    source_calls = 0

    def changing_record(root: Path):
        nonlocal source_calls
        records = original(root)
        if root == source and source_calls == 0:
            value.write_bytes(b"second")
        if root == source:
            source_calls += 1
        return records

    monkeypatch.setattr(adapter_module, "_record_tree", changing_record)
    inventory = adapter_module._copy_snapshot(source, destination)

    assert source_calls >= 4
    assert inventory == original(source)
    assert (destination / "value.bin").read_bytes() == b"second"


def test_snapshot_copy_fails_closed_when_source_never_stabilizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from greenhouse_manager import (
        t1_broker_identity_production_transaction_adapters as adapter_module,
    )

    source = tmp_path / "source"
    source.mkdir()
    value = source / "value.bin"
    value.write_bytes(b"0")
    destination = tmp_path / "snapshot"
    original = adapter_module._record_tree
    counter = 0

    def always_changing(root: Path):
        nonlocal counter
        records = original(root)
        if root == source:
            counter += 1
            value.write_bytes(str(counter).encode())
        return records

    monkeypatch.setattr(adapter_module, "_record_tree", always_changing)
    with pytest.raises(
        adapter_module.BrokerIdentityProductionTransactionAdaptersError,
        match="stable, verified inventory",
    ):
        adapter_module._copy_snapshot(source, destination, max_attempts=2)
    assert not destination.exists()
