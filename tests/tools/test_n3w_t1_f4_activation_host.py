from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_f4_activation_host.py"


def load_tool():
    name = "n3w_t1_f4_activation_host"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def package_binding(tool):
    return {
        "root": Path("/tmp/f4-package"),
        "manifest_sha256": "b" * 64,
        "source_head": "c" * 40,
        "files": {},
    }


def verified(tool):
    return {
        "status": "PASS",
        "state": "DEVICE_READY",
        "release_id": "a" * 40,
        "host_instance_id": "host-a",
        "system_id": "system-a",
        "production_service_start": False,
        "board_access": False,
    }


def test_command_surface_has_no_provisioning_replay_authority() -> None:
    tool = load_tool()
    source = TOOL.read_text(encoding="utf-8")

    assert tool.PREPARE_CONFIRMATION == "PREPARE F4 ACTIVATION: YES"
    assert tool.ACTIVATE_CONFIRMATION == "START F4 ACTIVATION: YES"
    assert 'subparsers.add_parser("audit")' in source
    assert 'subparsers.add_parser("prepare")' in source
    assert 'subparsers.add_parser("activate")' in source
    assert 'subparsers.add_parser("eligibility")' in source
    assert "START DEVICE PROVISIONING: YES" not in source
    assert 'PROVISION_CLI), "verify"' in source
    assert 'PROVISION_CLI), "start"' not in source


def test_factory_binding_requires_exact_release_host_and_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    current = verified(tool)
    exact = {
        "schema": tool.FACTORY_ACCEPTED_SCHEMA,
        "status": "PASS",
        "factory_accepted": True,
        "release_id": current["release_id"],
        "host_instance_id": current["host_instance_id"],
        "system_id": current["system_id"],
        "system_id_sha256": tool._sha256_text(current["system_id"]),
    }
    monkeypatch.setattr(tool, "_read_private_record", lambda _path: exact)

    result = tool._validate_factory_binding(current)

    assert result["factory_accepted"] is True

    drift = dict(exact)
    drift["host_instance_id"] = "host-b"
    monkeypatch.setattr(tool, "_read_private_record", lambda _path: drift)
    with pytest.raises(
        tool.F4Error,
        match="factory_acceptance_binding_invalid:host_instance_id",
    ):
        tool._validate_factory_binding(current)


def test_eligibility_is_phase_locked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    current = verified(tool)
    marker = {"factory_accepted": True}

    monkeypatch.setattr(tool, "_provision_verify", lambda: current)
    monkeypatch.setattr(tool, "_validate_factory_binding", lambda _v: marker)
    monkeypatch.setattr(tool, "_verify_installed_material", lambda _t: None)
    monkeypatch.setattr(
        tool,
        "_runtime_activity",
        lambda: {
            "production_service_start": False,
            "runtime_service_probe": "PASS",
            "running_services": [],
        },
    )

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {"stage": "PREPARED"},
    )
    with pytest.raises(tool.F4Error, match="broker:PREPARED"):
        tool._activation_eligibility("broker")
    with pytest.raises(tool.F4Error, match="services:PREPARED"):
        tool._activation_eligibility("services")

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {"stage": "BROKER_STARTING"},
    )
    assert tool._activation_eligibility("broker")["activation_eligible"] is True

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {"stage": "SERVICES_STARTING"},
    )
    assert tool._activation_eligibility("services")["activation_eligible"] is True

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {"stage": "RUNTIME_STARTED"},
    )
    assert tool._activation_eligibility("broker")["activation_eligible"] is True
    assert tool._activation_eligibility("services")["activation_eligible"] is True
    with pytest.raises(tool.F4Error, match="certificate:RUNTIME_STARTED"):
        tool._activation_eligibility("certificate")

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {"stage": "RUNTIME_ACCEPTED"},
    )
    assert tool._activation_eligibility("broker")["activation_eligible"] is True
    assert tool._activation_eligibility("services")["activation_eligible"] is True
    assert (
        tool._activation_eligibility("certificate")["activation_eligible"]
        is True
    )

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {"stage": "PERSISTENCE_ENABLED"},
    )
    assert tool._activation_eligibility("broker")["activation_eligible"] is True
    assert tool._activation_eligibility("services")["activation_eligible"] is True
    assert (
        tool._activation_eligibility("certificate")["activation_eligible"]
        is True
    )


def test_prepare_claims_before_factory_acceptance_and_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    audit = {
        "release_id": "a" * 40,
        "host_instance_id": "host-a",
        "system_id": "system-a",
        "system_id_sha256": tool._sha256_text("system-a"),
    }
    events: list[str] = []
    audit_calls = 0

    def factory_audit(*, require_claim_absent: bool):
        nonlocal audit_calls
        audit_calls += 1
        events.append(
            "audit_preclaim" if require_claim_absent else "audit_postclaim"
        )
        return dict(audit)

    def new_record(path: Path, _document):
        if path == tool.TRANSACTION_PATH:
            events.append("claim")
        elif path == tool.FACTORY_ACCEPTED_PATH:
            events.append("factory_accept")

    monkeypatch.setattr(
        tool,
        "_validate_package",
        lambda *_args, **_kwargs: package_binding(tool),
    )
    monkeypatch.setattr(tool, "_factory_audit", factory_audit)
    monkeypatch.setattr(tool, "_new_private_record", new_record)
    monkeypatch.setattr(
        tool,
        "_install_activation_material",
        lambda _package: events.append("install")
        or {
            "activation_material_installed": True,
            "installed_files": {},
        },
    )
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda stage, **_fields: events.append(stage) or {"stage": stage},
    )

    monkeypatch.setattr(tool, "_exclusive_f4", lambda: nullcontext())

    result = tool._prepare(
        tmp_path,
        tool.PREPARE_CONFIRMATION,
        "N3W_T1_F4_TEST_AUTH_01",
        "b" * 64,
        "c" * 40,
    )

    assert audit_calls == 2
    assert events == [
        "audit_preclaim",
        "claim",
        "audit_postclaim",
        "factory_accept",
        "install",
        "PREPARED",
    ]
    assert result["status"] == "PASS"
    assert result["production_service_start"] is False
    assert result["persistence_enabled"] is False
    assert result["authorization_consumed"] is True
    assert result["replay_allowed"] is False


def test_prepare_failure_consumes_and_stops(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    audit = {
        "release_id": "a" * 40,
        "host_instance_id": "host-a",
        "system_id": "system-a",
        "system_id_sha256": tool._sha256_text("system-a"),
    }
    stages: list[str] = []

    monkeypatch.setattr(
        tool,
        "_validate_package",
        lambda *_args, **_kwargs: package_binding(tool),
    )
    monkeypatch.setattr(
        tool,
        "_factory_audit",
        lambda **_kwargs: dict(audit),
    )
    monkeypatch.setattr(tool, "_new_private_record", lambda *_args: None)
    monkeypatch.setattr(
        tool,
        "_install_activation_material",
        lambda _root: (_ for _ in ()).throw(tool.F4Error("install_failed")),
    )
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda stage, **_fields: stages.append(stage) or {"stage": stage},
    )

    monkeypatch.setattr(tool, "_exclusive_f4", lambda: nullcontext())

    with pytest.raises(tool.F4Error, match="install_failed"):
        tool._prepare(
            tmp_path,
            tool.PREPARE_CONFIRMATION,
            "N3W_T1_F4_TEST_AUTH_02",
            "b" * 64,
            "c" * 40,
        )

    assert stages == ["STOPPED_PREPARE"]


def test_activate_orders_guard_broker_readiness_services_without_enable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    calls: list[tuple[str, ...]] = []
    stages: list[str] = []

    monkeypatch.setattr(tool, "_exclusive_f4", lambda: nullcontext())
    monkeypatch.setattr(
        tool,
        "_activation_eligibility",
        lambda phase: {
            "status": "PASS",
            "transaction_stage": "PREPARED",
            "eligibility_phase": phase,
        },
    )
    monkeypatch.setattr(
        tool,
        "_read_private_record",
        lambda _path: {"authorization_id": "N3W_T1_F4_TEST_AUTH_03"},
    )

    def run(argv, **_kwargs):
        calls.append(tuple(argv))
        return ""

    def systemctl(mode: str, unit: str):
        if mode == "is-active" and unit in {
            tool.GUARD_UNIT,
            tool.SERVICES_UNIT,
        }:
            return "active"
        return "unknown"

    monkeypatch.setattr(tool, "_run", run)
    monkeypatch.setattr(tool, "_systemctl", systemctl)
    monkeypatch.setattr(
        tool,
        "_running_services",
        lambda: frozenset({"broker", "manager", "homeassistant"}),
    )
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda stage, **_fields: stages.append(stage) or {"stage": stage},
    )

    result = tool._activate(
        tool.ACTIVATE_CONFIRMATION,
        "N3W_T1_F4_TEST_AUTH_03",
    )

    assert stages == [
        "BROKER_STARTING",
        "BROKER_READY",
        "SERVICES_STARTING",
        "RUNTIME_STARTED",
    ]
    assert ("systemctl", "start", tool.GUARD_UNIT) in calls
    assert ("systemctl", "start", tool.BROKER_UNIT) in calls
    assert ("systemctl", "start", tool.SERVICES_UNIT) in calls
    assert not any("enable" in call for call in calls)
    assert result["state"] == "RUNTIME_STARTED"
    assert result["runtime_acceptance_required"] is True
    assert result["persistence_enabled"] is False
    assert result["certificate_timer_enabled"] is False


def test_activation_failure_stops_started_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    calls: list[tuple[str, ...]] = []
    stages: list[str] = []

    monkeypatch.setattr(tool, "_exclusive_f4", lambda: nullcontext())
    monkeypatch.setattr(
        tool,
        "_activation_eligibility",
        lambda _phase: {"transaction_stage": "PREPARED"},
    )
    monkeypatch.setattr(
        tool,
        "_read_private_record",
        lambda _path: {"authorization_id": "N3W_T1_F4_TEST_AUTH_04"},
    )

    def run(argv, **_kwargs):
        call = tuple(argv)
        calls.append(call)
        if call == ("systemctl", "start", tool.SERVICES_UNIT):
            raise tool.F4Error("services_start_failed")
        return ""

    monkeypatch.setattr(tool, "_run", run)
    monkeypatch.setattr(
        tool,
        "_systemctl",
        lambda mode, unit: "active"
        if mode == "is-active" and unit == tool.GUARD_UNIT
        else "unknown",
    )
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda stage, **_fields: stages.append(stage) or {"stage": stage},
    )

    with pytest.raises(tool.F4Error, match="services_start_failed"):
        tool._activate(
            tool.ACTIVATE_CONFIRMATION,
            "N3W_T1_F4_TEST_AUTH_04",
        )

    assert ("systemctl", "stop", tool.SERVICES_UNIT) in calls
    assert ("systemctl", "stop", tool.BROKER_UNIT) in calls
    assert stages[-1] == "STOPPED_RUNTIME"
    assert "RUNTIME_STARTED" not in stages


def test_runtime_activity_fails_closed_when_compose_probe_is_unproven(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    compose = tmp_path / "docker-compose.yml"
    env = tmp_path / "docker-compose.env"
    compose.write_text("services: {}\n", encoding="utf-8")
    env.write_text("GH_SYSTEM_ID=test\n", encoding="utf-8")

    monkeypatch.setattr(tool, "COMPOSE_TARGET", compose)
    monkeypatch.setattr(tool, "COMPOSE_ENV", env)
    monkeypatch.setattr(tool, "_systemctl", lambda _mode, _unit: "inactive")
    monkeypatch.setattr(
        tool,
        "_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            tool.F4Error("probe_failed")
        ),
    )

    runtime = tool._runtime_activity()

    assert runtime["runtime_service_probe"] == "UNPROVEN"
    assert runtime["production_service_start"] is None
    assert runtime["running_services"] is None


def test_package_manifest_exact_binding_and_tamper_rejection(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    source_head = "d" * 40
    records = []
    for index, relative in enumerate(sorted(tool.INSTALL_MAP)):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"payload-{index}\n".encode()
        path.write_bytes(payload)
        records.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
        )
    manifest = {
        "schema": tool.PACKAGE_SCHEMA,
        "source_head": source_head,
        "files": records,
        "secret_values_included": False,
        "production_service_start": False,
        "board_access": False,
    }
    manifest_path = tmp_path / tool.PACKAGE_MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_sha = tool._sha256_file(manifest_path)

    package = tool._validate_package(
        tmp_path,
        expected_manifest_sha256=manifest_sha,
        expected_source_head=source_head,
    )

    assert package["source_head"] == source_head
    assert package["manifest_sha256"] == manifest_sha
    assert set(package["files"]) == set(tool.INSTALL_MAP)

    first = tmp_path / min(tool.INSTALL_MAP)
    first.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(tool.F4Error, match="package_file_binding_invalid"):
        tool._validate_package(
            tmp_path,
            expected_manifest_sha256=manifest_sha,
            expected_source_head=source_head,
        )


def test_installed_material_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    targets = [
        *(target for target, _mode in tool.INSTALL_MAP.values()),
        tool.COMPOSE_TARGET,
        tool.BROKER_ENV,
        tool.CERT_ENV,
    ]
    remapped = {}
    expected = {}
    for index, target in enumerate(targets):
        path = tmp_path / f"target-{index}"
        path.write_text(f"target-{index}\n", encoding="utf-8")
        remapped[str(target)] = path
        expected[str(target)] = tool._file_binding(path)

    original = tool._file_binding

    def binding(path: Path):
        mapped = remapped.get(str(path))
        if mapped is None:
            return original(path)
        return original(mapped)

    monkeypatch.setattr(tool, "_file_binding", binding)
    tool._verify_installed_material({"installed_files": expected})

    remapped[str(targets[0])].write_text("drift\n", encoding="utf-8")
    with pytest.raises(tool.F4Error, match="installed_material_drift"):
        tool._verify_installed_material({"installed_files": expected})


def test_authorization_id_is_bound_and_invalid_ids_fail() -> None:
    tool = load_tool()
    audit = {
        "release_id": "a" * 40,
        "host_instance_id": "host-a",
        "system_id": "system-a",
        "system_id_sha256": tool._sha256_text("system-a"),
    }

    document = tool._transaction_document(
        audit,
        "N3W_T1_F4_LIVE_AUTH_01",
        package_binding(tool),
    )
    assert document["authorization_id"] == "N3W_T1_F4_LIVE_AUTH_01"
    assert document["authorization_consumed"] is True
    assert document["replay_allowed"] is False

    with pytest.raises(tool.F4Error, match="authorization_id_invalid"):
        tool._transaction_document(
            audit,
            "bad authorization",
            package_binding(tool),
        )


def test_f4_execution_has_single_initializer_lock() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "fcntl.LOCK_EX | fcntl.LOCK_NB" in source
    assert "f4_operation_already_running" in source
    assert "with _exclusive_f4():" in source


def test_fresh_certificate_binding_has_no_fixed_fingerprint() -> None:
    tool = load_tool()
    payload = tool._certificate_env_payload()

    assert "/opt/greenhouse-secrets/broker-ca/ca.key" in payload
    assert "/var/lib/greenhouse-manager/identity/system-ca.pem" in payload
    assert "N3WFC4_CERT_SERVER_NAME=armbian" in payload
    assert "N3WFC4_CERT_ALLOWED_ROOT_BROKER_CA=/opt/greenhouse-secrets/broker-ca" in payload
    assert "b305f61656a0e795" not in payload
    assert "8272aa061d70bf0b" not in payload
    assert "745c29f156b35cdb" not in payload


def test_systemd_activation_units_fail_closed_on_f4_phase() -> None:
    broker = (
        ROOT / "infra/n3w-t1/f4/n3wfc4-broker-activation.service"
    ).read_text(encoding="utf-8")
    services = (
        ROOT / "infra/n3w-t1/f4/n3wfc4-services-activation.service"
    ).read_text(encoding="utf-8")
    certificate = (
        ROOT
        / "infra/n3w-t1/f4/n3wfc4-broker-certificate-lifecycle.service"
    ).read_text(encoding="utf-8")

    assert (
        "ExecStartPre=/usr/local/sbin/n3w-t1-f4-activation "
        "eligibility --phase broker"
        in broker
    )
    assert (
        "ExecStartPre=/usr/local/sbin/n3w-t1-f4-activation "
        "eligibility --phase services"
        in services
    )
    assert (
        "ExecStartPre=/usr/local/sbin/n3w-t1-f4-activation "
        "eligibility --phase certificate"
        in certificate
    )
    assert "N3WFC4_CERT_ALLOWED_ROOT_BROKER_CA" in certificate


def test_persistence_helper_remains_enable_only() -> None:
    script = (
        ROOT / "infra/n3w-t1/activate-systemd-production.sh"
    ).read_text(encoding="utf-8")

    assert "systemctl enable" in script
    assert "enable --now" not in script
    assert "systemctl start" not in script
    assert "systemctl restart" not in script
