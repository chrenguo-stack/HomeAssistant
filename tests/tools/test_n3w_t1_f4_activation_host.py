from __future__ import annotations

import hashlib
import importlib.util
import json
import os
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

    assert TOOL.read_bytes().startswith(b"#!/usr/bin/python3\n")
    assert os.access(TOOL, os.X_OK)
    assert tool.PREPARE_CONFIRMATION == "PREPARE F4 ACTIVATION: YES"
    assert tool.ACTIVATE_CONFIRMATION == "START F4 ACTIVATION: YES"
    assert (
        tool.CONTROL_REPAIR_CONFIRMATION
        == "REPAIR F4 CONTROL MATERIAL: YES"
    )
    assert 'subparsers.add_parser("audit")' in source
    assert 'subparsers.add_parser("prepare")' in source
    assert 'subparsers.add_parser("activate")' in source
    assert 'subparsers.add_parser("repair-prepared-control")' in source
    assert '"repair-prepared-activation-authority"' in source
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
    tmp_path: Path,
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
        lambda _v: {
            "stage": "PREPARED",
            "package_source_head": "c" * 40,
            "package_manifest_sha256": "b" * 64,
        },
    )
    with pytest.raises(tool.F4Error, match="broker:PREPARED"):
        tool._activation_eligibility("broker")
    with pytest.raises(tool.F4Error, match="services:PREPARED"):
        tool._activation_eligibility("services")

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {
            "stage": "BROKER_STARTING",
            "package_source_head": "c" * 40,
            "package_manifest_sha256": "b" * 64,
        },
    )
    assert tool._activation_eligibility("broker")["activation_eligible"] is True

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {
            "stage": "SERVICES_STARTING",
            "package_source_head": "c" * 40,
            "package_manifest_sha256": "b" * 64,
        },
    )
    assert tool._activation_eligibility("services")["activation_eligible"] is True

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {
            "stage": "RUNTIME_STARTED",
            "package_source_head": "c" * 40,
            "package_manifest_sha256": "b" * 64,
        },
    )
    assert tool._activation_eligibility("broker")["activation_eligible"] is True
    assert tool._activation_eligibility("services")["activation_eligible"] is True
    with pytest.raises(tool.F4Error, match="certificate:RUNTIME_STARTED"):
        tool._activation_eligibility("certificate")

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {
            "stage": "RUNTIME_ACCEPTED",
            "package_source_head": "c" * 40,
            "package_manifest_sha256": "b" * 64,
        },
    )
    assert tool._activation_eligibility("broker")["activation_eligible"] is True
    assert tool._activation_eligibility("services")["activation_eligible"] is True
    with pytest.raises(tool.F4Error, match="certificate:RUNTIME_ACCEPTED"):
        tool._activation_eligibility("certificate")

    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {
            "stage": "PERSISTENCE_ENABLED",
            "package_source_head": "c" * 40,
            "package_manifest_sha256": "b" * 64,
        },
    )
    assert tool._activation_eligibility("broker")["activation_eligible"] is True
    assert tool._activation_eligibility("services")["activation_eligible"] is True
    with pytest.raises(tool.F4Error, match="certificate_runtime_not_authorized"):
        tool._activation_eligibility("certificate")

    status_file = tmp_path / "status.json"
    status_file.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(tool, "CERT_STATUS_FILE", status_file)
    status_sha = tool._sha256_file(status_file)
    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: {
            "stage": "PERSISTENCE_ENABLED",
            "package_source_head": "c" * 40,
            "package_manifest_sha256": "b" * 64,
            "broker_services_persistence_enabled": True,
            "certificate_first_audit_passed": True,
            "certificate_timer_enabled": True,
            "pre_reboot_ready": True,
            "certificate_status_sha256": status_sha,
        },
    )
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
        lambda _path: {
            "authorization_id": "N3W_T1_F4_PREPARE_TEST_AUTH_03",
            "control_repair_authorization_id": (
                "N3W_T1_F4_CONTROL_REPAIR_TEST_AUTH_03"
            ),
        },
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
        "N3W_T1_F4_ACTIVATE_TEST_AUTH_03",
    )

    assert stages == [
        "ACTIVATION_CLAIMED",
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
    assert result["authorization_id"] == "N3W_T1_F4_ACTIVATE_TEST_AUTH_03"
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
        lambda _path: {
            "authorization_id": "N3W_T1_F4_PREPARE_TEST_AUTH_04"
        },
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
            "N3W_T1_F4_ACTIVATE_TEST_AUTH_04",
        )

    assert ("systemctl", "stop", tool.SERVICES_UNIT) in calls
    assert ("systemctl", "stop", tool.BROKER_UNIT) in calls
    assert stages[-1] == "STOPPED_RUNTIME"
    assert "RUNTIME_STARTED" not in stages


def test_activate_requires_distinct_successor_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(tool, "_exclusive_f4", lambda: nullcontext())
    monkeypatch.setattr(
        tool,
        "_activation_eligibility",
        lambda _phase: {"transaction_stage": "PREPARED"},
    )
    monkeypatch.setattr(
        tool,
        "_read_private_record",
        lambda _path: {
            "authorization_id": "N3W_T1_F4_PREPARE_AUTH",
            "control_repair_authorization_id": "N3W_T1_F4_REPAIR_AUTH",
            "activation_authority_repair_authorization_id": (
                "N3W_T1_F4_ACTIVATION_AUTHORITY_REPAIR_AUTH"
            ),
        },
    )

    with pytest.raises(
        tool.F4Error,
        match="activation_authorization_not_distinct",
    ):
        tool._activate(
            tool.ACTIVATE_CONFIRMATION,
            "N3W_T1_F4_PREPARE_AUTH",
        )

    with pytest.raises(
        tool.F4Error,
        match="activation_authorization_not_distinct",
    ):
        tool._activate(
            tool.ACTIVATE_CONFIRMATION,
            "N3W_T1_F4_REPAIR_AUTH",
        )


    with pytest.raises(
        tool.F4Error,
        match="activation_authorization_not_distinct",
    ):
        tool._activate(
            tool.ACTIVATE_CONFIRMATION,
            "N3W_T1_F4_ACTIVATION_AUTHORITY_REPAIR_AUTH",
        )

def test_activate_claims_successor_authorization_before_live_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    order: list[str] = []
    monkeypatch.setattr(tool, "_exclusive_f4", lambda: nullcontext())
    monkeypatch.setattr(
        tool,
        "_activation_eligibility",
        lambda _phase: {"transaction_stage": "PREPARED"},
    )
    monkeypatch.setattr(
        tool,
        "_read_private_record",
        lambda _path: {
            "authorization_id": "N3W_T1_F4_PREPARE_AUTH",
        },
    )

    def advance(stage, **_fields):
        order.append(stage)
        return {"stage": stage}

    def run(argv, **_kwargs):
        order.append("RUN:" + ":".join(argv))
        raise tool.F4Error("guard_start_failed")

    monkeypatch.setattr(tool, "_advance_transaction", advance)
    monkeypatch.setattr(tool, "_run", run)
    monkeypatch.setattr(
        tool,
        "_runtime_activity",
        lambda: {
            "production_service_start": False,
            "running_services": [],
        },
    )

    with pytest.raises(tool.F4Error, match="guard_start_failed"):
        tool._activate(
            tool.ACTIVATE_CONFIRMATION,
            "N3W_T1_F4_ACTIVATE_NEW_AUTH",
        )

    assert order[0] == "ACTIVATION_CLAIMED"
    assert order[1].startswith("RUN:systemctl:start:")


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


def test_runtime_continuation_command_surface() -> None:
    load_tool()
    source = TOOL.read_text(encoding="utf-8")

    for command in (
        "accept-runtime",
        "enable-persistence",
        "certificate-audit",
        "enable-certificate-timer",
    ):
        assert f'"{command}"' in source
    assert "activate-systemd-production.sh" not in source


def test_accept_runtime_advances_only_after_report_persisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    events: list[str] = []
    verified_state = verified(tool)
    transaction = {
        "authorization_id": "N3W_T1_F4_TEST_AUTH_05",
        "stage": "RUNTIME_STARTED",
    }
    report = {
        "homeassistant": {"entry_id_sha256": "e" * 64},
    }

    monkeypatch.setattr(tool, "_exclusive_f4", lambda: nullcontext())
    monkeypatch.setattr(tool, "_provision_verify", lambda: verified_state)
    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _verified: transaction,
    )
    monkeypatch.setattr(
        tool,
        "_runtime_acceptance_report",
        lambda: events.append("acceptance") or report,
    )
    monkeypatch.setattr(
        tool,
        "_new_private_record",
        lambda path, _document: events.append(f"persist:{path.name}"),
    )
    monkeypatch.setattr(
        tool,
        "_sha256_file",
        lambda _path: "f" * 64,
    )
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda stage, **_fields: events.append(f"advance:{stage}")
        or {"stage": stage},
    )

    result = tool._accept_runtime("N3W_T1_F4_TEST_AUTH_05")

    assert events == [
        "acceptance",
        f"persist:{tool.RUNTIME_ACCEPTANCE_PATH.name}",
        "advance:RUNTIME_ACCEPTED",
    ]
    assert result["state"] == "RUNTIME_ACCEPTED"
    assert result["persistence_enabled"] is False
    assert result["certificate_timer_enabled"] is False


def test_accept_runtime_failure_uses_fail_closed_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    verified_state = verified(tool)
    transaction = {
        "authorization_id": "N3W_T1_F4_TEST_AUTH_06",
        "stage": "RUNTIME_STARTED",
    }
    rollback: list[str] = []

    monkeypatch.setattr(tool, "_exclusive_f4", lambda: nullcontext())
    monkeypatch.setattr(tool, "_provision_verify", lambda: verified_state)
    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _verified: transaction,
    )
    monkeypatch.setattr(
        tool,
        "_runtime_acceptance_report",
        lambda: (_ for _ in ()).throw(tool.F4Error("acceptance_failed")),
    )
    monkeypatch.setattr(
        tool,
        "_downstream_fail_closed",
        lambda stage, _error: rollback.append(stage),
    )

    with pytest.raises(tool.F4Error, match="acceptance_failed"):
        tool._accept_runtime("N3W_T1_F4_TEST_AUTH_06")

    assert rollback == ["RUNTIME_ACCEPTANCE"]


def test_persistence_enables_only_broker_and_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    verified_state = verified(tool)
    transaction = {
        "authorization_id": "N3W_T1_F4_TEST_AUTH_07",
        "stage": "RUNTIME_ACCEPTED",
        "runtime_acceptance_passed": True,
    }
    calls: list[tuple[str, ...]] = []
    enabled: set[str] = set()

    monkeypatch.setattr(tool, "_exclusive_f4", lambda: nullcontext())
    monkeypatch.setattr(tool, "_provision_verify", lambda: verified_state)
    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _verified: transaction,
    )
    monkeypatch.setattr(tool, "_validate_factory_binding", lambda _verified: {})
    monkeypatch.setattr(tool, "_verify_installed_material", lambda _tx: None)
    monkeypatch.setattr(
        tool,
        "_validate_runtime_acceptance_binding",
        lambda _tx: {"status": "PASS"},
    )
    monkeypatch.setattr(
        tool,
        "_runtime_container_snapshot",
        lambda: {
            "broker": {"id": "b", "started_at": "1"},
            "manager": {"id": "m", "started_at": "1"},
            "homeassistant": {"id": "h", "started_at": "1"},
        },
    )
    monkeypatch.setattr(
        tool,
        "_runtime_activity",
        lambda: {
            "production_service_start": True,
            "running_services": ["broker", "homeassistant", "manager"],
        },
    )

    def run(argv, **_kwargs):
        call = tuple(argv)
        calls.append(call)
        if call[:2] == ("systemctl", "enable"):
            enabled.update(call[2:])
        return ""

    monkeypatch.setattr(tool, "_run", run)
    monkeypatch.setattr(
        tool,
        "_systemctl",
        lambda mode, unit: (
            "enabled"
            if mode == "is-enabled" and unit in enabled
            else "disabled"
        ),
    )
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda stage, **_fields: {"stage": stage},
    )

    result = tool._enable_persistence("N3W_T1_F4_TEST_AUTH_07")

    assert (
        "systemctl",
        "enable",
        tool.BROKER_UNIT,
        tool.SERVICES_UNIT,
    ) in calls
    assert tool.CERT_TIMER not in enabled
    assert result["state"] == "PERSISTENCE_ENABLED"
    assert result["certificate_timer_enabled"] is False


def test_certificate_first_audit_uses_audit_not_auto_renew() -> None:
    tool = load_tool()
    command = tool._certificate_audit_command()

    assert command[1] == "audit"
    assert "auto-renew" not in command
    assert str(tool.CA_KEY.parent) in command
    assert str(tool.SYSTEM_CA.parent) in command


def test_certificate_timer_enable_is_enable_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    verified_state = verified(tool)
    transaction = {
        "authorization_id": "N3W_T1_F4_TEST_AUTH_08",
        "stage": "PERSISTENCE_ENABLED",
        "certificate_first_audit_passed": True,
        "certificate_status_sha256": "a" * 64,
    }
    calls: list[tuple[str, ...]] = []
    enabled = False

    monkeypatch.setattr(tool, "_exclusive_f4", lambda: nullcontext())
    monkeypatch.setattr(tool, "_provision_verify", lambda: verified_state)
    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _verified: transaction,
    )
    monkeypatch.setattr(tool, "_validate_factory_binding", lambda _verified: {})
    monkeypatch.setattr(tool, "_verify_installed_material", lambda _tx: None)
    monkeypatch.setattr(
        tool,
        "_validate_runtime_acceptance_binding",
        lambda _tx: {"status": "PASS"},
    )
    monkeypatch.setattr(tool, "_sha256_file", lambda _path: "a" * 64)
    monkeypatch.setattr(
        tool,
        "_certificate_identity_snapshot",
        lambda: {
            "server_cert": "1",
            "server_key": "2",
            "ca_cert": "3",
            "ca_key": "4",
            "system_ca": "5",
        },
    )
    monkeypatch.setattr(
        tool,
        "_runtime_container_snapshot",
        lambda: {
            "broker": {"id": "b", "started_at": "1"},
            "manager": {"id": "m", "started_at": "1"},
            "homeassistant": {"id": "h", "started_at": "1"},
        },
    )

    def systemctl(mode: str, unit: str):
        if unit == tool.CERT_TIMER and mode == "is-enabled":
            return "enabled" if enabled else "disabled"
        if unit == tool.CERT_TIMER and mode == "is-active":
            return "inactive"
        if unit == tool.CERT_SERVICE and mode == "is-active":
            return "inactive"
        if unit in {tool.BROKER_UNIT, tool.SERVICES_UNIT} and mode == "is-enabled":
            return "enabled"
        return "unknown"

    def run(argv, **_kwargs):
        nonlocal enabled
        call = tuple(argv)
        calls.append(call)
        if call == ("systemctl", "enable", tool.CERT_TIMER):
            enabled = True
        return ""

    monkeypatch.setattr(tool, "_systemctl", systemctl)
    monkeypatch.setattr(tool, "_run", run)
    monkeypatch.setattr(
        tool,
        "_runtime_activity",
        lambda: {
            "production_service_start": True,
            "running_services": ["broker", "homeassistant", "manager"],
        },
    )
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda stage, **_fields: {"stage": stage},
    )

    result = tool._enable_certificate_timer(
        "N3W_T1_F4_TEST_AUTH_08"
    )

    assert calls == [("systemctl", "enable", tool.CERT_TIMER)]
    assert result["state"] == "PRE_REBOOT_READY"
    assert result["certificate_timer_enabled"] is True
    assert result["certificate_timer_active_before_reboot"] is False


def test_service_identity_runtime_binding_requires_exact_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    identities = {
        "manager": {
            "service": "manager",
            "system_id": "system-a",
            "generation": 1,
            "username": "manager-user",
            "client_id": "manager-client",
        },
        "provisioning": {
            "service": "provisioning",
            "system_id": "system-a",
            "generation": 1,
            "username": "provision-user",
            "client_id": "provision-client",
        },
        "homeassistant": {
            "service": "homeassistant",
            "system_id": "system-a",
            "generation": 1,
            "username": "ha-user",
            "client_id": "ha-client",
        },
    }
    bootstrap = {
        "schema": "gh.n3w.t1-clean-homeassistant-mqtt-bootstrap/1",
        "service": "homeassistant",
        "broker": "127.0.0.1",
        "port": 1883,
        "protocol": "5",
        "username": "ha-user",
        "client_id": "ha-client",
        "generation": 1,
        "official_config_flow_only": True,
        "direct_storage_edit_forbidden": True,
        "automatic_apply": True,
        "runtime_verified": False,
    }

    def private_json(path, **_kwargs):
        if path.name == "mqtt-bootstrap.json":
            return bootstrap
        return identities[path.parent.name]

    monkeypatch.setattr(tool, "_private_service_json", private_json)
    document = {
        "Config": {
            "Env": [
                "GH_SYSTEM_ID=system-a",
                "GH_MQTT_USERNAME=manager-user",
                "GH_MQTT_CLIENT_ID=manager-client",
                "GH_N3W_PROVISIONING_USERNAME=provision-user",
                "GH_N3W_PROVISIONING_CLIENT_ID=provision-client",
            ]
        }
    }

    report = tool._service_identity_runtime_binding(
        document,
        expected_system_id="system-a",
    )

    assert report["manager_identity_exact"] is True
    assert report["homeassistant_bootstrap_identity_exact"] is True

    document["Config"]["Env"][1] = "GH_MQTT_USERNAME=provision-user"
    with pytest.raises(tool.F4Error, match="service_identity_drift"):
        tool._service_identity_runtime_binding(
            document,
            expected_system_id="system-a",
        )


def test_product_container_guard_rejects_extra_product_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    release = {
        "images": {
            "broker": {"image": "broker:image"},
            "manager": {"image": "manager:image"},
            "homeassistant": {"image": "ha:image"},
        }
    }
    inspects = {
        "broker": {"Id": "b"},
        "manager": {"Id": "m"},
        "homeassistant": {"Id": "h"},
    }

    def run(argv, **_kwargs):
        if argv[:3] == ("docker", "ps", "--format"):
            return "b\nm\nh\nx\n"
        if argv[:2] == ("docker", "inspect"):
            return json.dumps(
                [
                    {"Id": "b", "Config": {"Image": "broker:image"}},
                    {"Id": "m", "Config": {"Image": "manager:image"}},
                    {"Id": "h", "Config": {"Image": "ha:image"}},
                    {"Id": "x", "Config": {"Image": "other:image"}},
                ]
            )
        raise AssertionError(argv)

    monkeypatch.setattr(tool, "_run", run)
    report = tool._product_container_guard(release, inspects)
    assert report["unexpected_product_container_count"] == 0

    def run_extra(argv, **_kwargs):
        if argv[:3] == ("docker", "ps", "--format"):
            return "b\nm\nh\nx\n"
        if argv[:2] == ("docker", "inspect"):
            return json.dumps(
                [
                    {"Id": "b", "Config": {"Image": "broker:image"}},
                    {"Id": "m", "Config": {"Image": "manager:image"}},
                    {"Id": "h", "Config": {"Image": "ha:image"}},
                    {"Id": "x", "Config": {"Image": "manager:image"}},
                ]
            )
        raise AssertionError(argv)

    monkeypatch.setattr(tool, "_run", run_extra)
    with pytest.raises(tool.F4Error, match="unexpected_product_container"):
        tool._product_container_guard(release, inspects)


def test_downstream_rollback_requires_listener_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    stages: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(tool, "_run", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        tool,
        "_runtime_activity",
        lambda: {
            "production_service_start": False,
            "running_services": [],
        },
    )
    monkeypatch.setattr(
        tool,
        "_systemctl",
        lambda mode, _unit: "disabled" if mode == "is-enabled" else "inactive",
    )
    monkeypatch.setattr(tool, "_product_listener_ports", lambda: [8883])
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda stage, **fields: stages.append((stage, fields)) or fields,
    )

    tool._downstream_fail_closed("TEST", tool.F4Error("failed"))

    assert stages[-1][0] == "STOPPED_TEST_ROLLBACK_UNPROVEN"
    assert stages[-1][1]["rollback_proven"] is False
    assert stages[-1][1]["product_listener_ports"] == [8883]


def test_prepared_control_repair_rebinds_only_launcher(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    package_root = tmp_path / "package"
    launcher_relative = "tools/n3w_t1_f4_activation_host.py"
    launcher_source = package_root / launcher_relative
    launcher_source.parent.mkdir(parents=True)
    launcher_source.write_text(
        "#!/usr/bin/python3\nprint('ok')\n",
        encoding="utf-8",
    )
    launcher_sha = tool._sha256_file(launcher_source)

    package_files = {}
    installed_files = {}
    for relative, (target, mode) in tool.INSTALL_MAP.items():
        if relative == launcher_relative:
            package_files[relative] = {
                "sha256": launcher_sha,
                "size": launcher_source.stat().st_size,
            }
            installed_files[str(target)] = {
                "sha256": tool.CONTROL_REPAIR_DEFECT_LAUNCHER_SHA256,
                "size": 100,
                "mode": mode,
                "uid": 0,
                "gid": 0,
            }
        else:
            package_files[relative] = {"sha256": "d" * 64, "size": 10}
            installed_files[str(target)] = {
                "sha256": "d" * 64,
                "size": 10,
                "mode": mode,
                "uid": 0,
                "gid": 0,
            }
    for target in (tool.COMPOSE_TARGET, tool.BROKER_ENV, tool.CERT_ENV):
        installed_files[str(target)] = {
            "sha256": "e" * 64,
            "size": 20,
            "mode": 0o600,
            "uid": 0,
            "gid": 0,
        }

    transaction = {
        "stage": "PREPARED",
        "authorization_id": "N3W_T1_F4_PREPARE_TEST",
        "package_source_head": tool.CONTROL_REPAIR_DEFECT_SOURCE_HEAD,
        "package_manifest_sha256": tool.CONTROL_REPAIR_DEFECT_MANIFEST_SHA256,
        "installed_files": installed_files,
    }
    package = {
        "root": package_root,
        "manifest_sha256": "f" * 64,
        "source_head": "1" * 40,
        "files": package_files,
    }
    stages = []

    monkeypatch.setattr(tool, "_validate_package", lambda *_a, **_k: package)
    monkeypatch.setattr(tool, "_exclusive_f4", nullcontext)
    monkeypatch.setattr(tool, "_provision_verify", lambda: verified(tool))
    monkeypatch.setattr(tool, "_validate_factory_binding", lambda _v: {})
    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: transaction,
    )
    monkeypatch.setattr(tool, "_verify_installed_material", lambda _t: None)
    monkeypatch.setattr(
        tool,
        "_runtime_activity",
        lambda: {
            "production_service_start": False,
            "running_services": [],
        },
    )
    monkeypatch.setattr(tool, "_product_listener_ports", list)
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda stage, **fields: stages.append((stage, fields))
        or {**transaction, **fields, "stage": stage},
    )

    def replace_file(
        source,
        target,
        mode,
        *,
        expected_current,
        expected_sha256,
        expected_size,
    ):
        assert source == launcher_source
        assert target == tool.INSTALL_MAP[launcher_relative][0]
        assert mode == 0o755
        assert (
            expected_current["sha256"]
            == tool.CONTROL_REPAIR_DEFECT_LAUNCHER_SHA256
        )
        assert expected_sha256 == launcher_sha
        assert expected_size == launcher_source.stat().st_size

    monkeypatch.setattr(tool, "_atomic_replace_bound_file", replace_file)
    monkeypatch.setattr(
        tool,
        "_file_binding",
        lambda _path: {
            "sha256": launcher_sha,
            "size": launcher_source.stat().st_size,
            "mode": 0o755,
            "uid": 0,
            "gid": 0,
        },
    )
    monkeypatch.setattr(
        tool,
        "_read_private_record",
        lambda _path: {
            **transaction,
            "installed_files": {
                **installed_files,
                str(tool.INSTALL_MAP[launcher_relative][0]): {
                    "sha256": launcher_sha,
                    "size": launcher_source.stat().st_size,
                    "mode": 0o755,
                    "uid": 0,
                    "gid": 0,
                },
            },
        },
    )

    report = tool._repair_prepared_control(
        package_root,
        tool.CONTROL_REPAIR_CONFIRMATION,
        "N3W_T1_F4_CONTROL_REPAIR_TEST",
        "f" * 64,
        "1" * 40,
    )

    assert stages[0][0] == "CONTROL_REPAIR_CLAIMED"
    assert stages[-1][0] == "PREPARED"
    assert report["control_repair_passed"] is True
    assert report["control_repair_authorization_consumed"] is True
    assert report["control_repair_replay_allowed"] is False


def test_prepared_activation_authority_repair_rebinds_only_launcher(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    package_root = tmp_path / "package"
    launcher_relative = "tools/n3w_t1_f4_activation_host.py"
    launcher_source = package_root / launcher_relative
    launcher_source.parent.mkdir(parents=True)
    launcher_source.write_text(
        "#!/usr/bin/python3\nprint('new activation authority')\n",
        encoding="utf-8",
    )
    launcher_sha = tool._sha256_file(launcher_source)

    package_files = {}
    installed_files = {}
    for relative, (target, mode) in tool.INSTALL_MAP.items():
        if relative == launcher_relative:
            package_files[relative] = {
                "sha256": launcher_sha,
                "size": launcher_source.stat().st_size,
            }
            installed_files[str(target)] = {
                "sha256": (
                    tool.ACTIVATION_AUTHORITY_REPAIR_FROM_LAUNCHER_SHA256
                ),
                "size": 100,
                "mode": mode,
                "uid": 0,
                "gid": 0,
            }
        else:
            package_files[relative] = {"sha256": "d" * 64, "size": 10}
            installed_files[str(target)] = {
                "sha256": "d" * 64,
                "size": 10,
                "mode": mode,
                "uid": 0,
                "gid": 0,
            }
    for target in (tool.COMPOSE_TARGET, tool.BROKER_ENV, tool.CERT_ENV):
        installed_files[str(target)] = {
            "sha256": "e" * 64,
            "size": 20,
            "mode": 0o600,
            "uid": 0,
            "gid": 0,
        }

    transaction = {
        "stage": "PREPARED",
        "authorization_id": "N3W_T1_F4_PREPARE_TEST",
        "control_repair_authorization_id": "N3W_T1_F4_REPAIR_TEST",
        "control_repair_passed": True,
        "package_source_head": (
            tool.ACTIVATION_AUTHORITY_REPAIR_FROM_SOURCE_HEAD
        ),
        "package_manifest_sha256": (
            tool.ACTIVATION_AUTHORITY_REPAIR_FROM_MANIFEST_SHA256
        ),
        "installed_files": installed_files,
    }
    package = {
        "root": package_root,
        "manifest_sha256": "f" * 64,
        "source_head": "1" * 40,
        "files": package_files,
    }
    stages = []

    monkeypatch.setattr(tool, "_validate_package", lambda *_a, **_k: package)
    monkeypatch.setattr(tool, "_exclusive_f4", nullcontext)
    monkeypatch.setattr(tool, "_provision_verify", lambda: verified(tool))
    monkeypatch.setattr(tool, "_validate_factory_binding", lambda _v: {})
    monkeypatch.setattr(
        tool,
        "_validate_transaction_binding",
        lambda _v: transaction,
    )
    monkeypatch.setattr(tool, "_verify_installed_material", lambda _t: None)
    monkeypatch.setattr(
        tool,
        "_runtime_activity",
        lambda: {
            "production_service_start": False,
            "running_services": [],
        },
    )
    monkeypatch.setattr(tool, "_product_listener_ports", list)
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda stage, **fields: stages.append((stage, fields))
        or {**transaction, **fields, "stage": stage},
    )

    def replace_file(
        source,
        target,
        mode,
        *,
        expected_current,
        expected_sha256,
        expected_size,
    ):
        assert source == launcher_source
        assert target == tool.INSTALL_MAP[launcher_relative][0]
        assert mode == 0o755
        assert expected_current["sha256"] == (
            tool.ACTIVATION_AUTHORITY_REPAIR_FROM_LAUNCHER_SHA256
        )
        assert expected_sha256 == launcher_sha
        assert expected_size == launcher_source.stat().st_size

    monkeypatch.setattr(tool, "_atomic_replace_bound_file", replace_file)
    monkeypatch.setattr(
        tool,
        "_file_binding",
        lambda _path: {
            "sha256": launcher_sha,
            "size": launcher_source.stat().st_size,
            "mode": 0o755,
            "uid": 0,
            "gid": 0,
        },
    )
    monkeypatch.setattr(
        tool,
        "_read_private_record",
        lambda _path: {
            **transaction,
            "installed_files": {
                **installed_files,
                str(tool.INSTALL_MAP[launcher_relative][0]): {
                    "sha256": launcher_sha,
                    "size": launcher_source.stat().st_size,
                    "mode": 0o755,
                    "uid": 0,
                    "gid": 0,
                },
            },
        },
    )

    report = tool._repair_prepared_activation_authority(
        package_root,
        tool.ACTIVATION_AUTHORITY_REPAIR_CONFIRMATION,
        "N3W_T1_F4_ACTIVATION_AUTHORITY_REPAIR_TEST",
        "f" * 64,
        "1" * 40,
    )

    assert stages[0][0] == "ACTIVATION_AUTHORITY_REPAIR_CLAIMED"
    assert stages[-1][0] == "PREPARED"
    assert report["activation_authority_repair_passed"] is True
    assert (
        report["activation_authority_repair_authorization_consumed"]
        is True
    )
    assert report["activation_authority_repair_replay_allowed"] is False


def test_mount_contract_ignores_only_tmpfs_and_binds_exact_source(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    document = {
        "Mounts": [
            {
                "Type": "bind",
                "Source": "/source/a",
                "Destination": "/target/a",
                "RW": False,
            },
            {
                "Type": "tmpfs",
                "Source": "",
                "Destination": "/tmp",
                "RW": True,
            },
        ]
    }

    tool._mount_contract(
        document,
        {"/target/a": ("/source/a", False)},
        label="test",
    )

    document["Mounts"][0]["Source"] = "/source/drift"
    with pytest.raises(tool.F4Error, match="mount_contract_invalid"):
        tool._mount_contract(
            document,
            {"/target/a": ("/source/a", False)},
            label="test",
        )


def test_manager_tmpfs_contract_accepts_semantic_sizes() -> None:
    tool = load_tool()

    tool._manager_tmpfs_contract(
        {
            "Tmpfs": {
                "/tmp": "size=16m,mode=1777",
                "/run/greenhouse-manager": (
                    "size=4194304,mode=0700,uid=999,gid=999"
                ),
            }
        }
    )

    with pytest.raises(tool.F4Error, match="manager_tmpfs_contract_invalid"):
        tool._manager_tmpfs_contract(
            {
                "Tmpfs": {
                    "/tmp": "size=16m,mode=1777",
                    "/run/greenhouse-manager": (
                        "size=4m,mode=0700,uid=0,gid=999"
                    ),
                }
            }
        )


def test_broker_extra_unbound_exposed_port_is_allowed() -> None:
    tool = load_tool()
    document = {
        "NetworkSettings": {
            "Networks": {
                "n3wfc4-private": {},
                "n3wfc4-services": {},
            },
            "Ports": {
                "1883/tcp": [
                    {"HostIp": "127.0.0.1", "HostPort": "1883"}
                ],
                "8883/tcp": [
                    {"HostIp": "0.0.0.0", "HostPort": "8883"}
                ],
                "9001/tcp": None,
            },
        },
        "HostConfig": {},
    }

    tool._broker_runtime_contract(document)

    document["NetworkSettings"]["Ports"]["9001/tcp"] = [
        {"HostIp": "0.0.0.0", "HostPort": "9001"}
    ]
    with pytest.raises(tool.F4Error, match="unexpected_publication"):
        tool._broker_runtime_contract(document)


def test_manager_runtime_stability_requires_same_container_and_one_mqtt_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    clock = iter([0.0, 10.0])
    monkeypatch.setattr(tool.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(tool.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        tool,
        "_compose_service_inspect",
        lambda _service: {
            "Id": "manager-container",
            "State": {
                "Running": True,
                "StartedAt": "2026-10-15T00:00:00Z",
            },
        },
    )
    monkeypatch.setattr(
        tool,
        "_container_established_socket_count",
        lambda _container, _port: 1,
    )

    report = tool._manager_runtime_stability(
        "manager",
        expected_id="manager-container",
        expected_started_at="2026-10-15T00:00:00Z",
    )

    assert report["container_identity_stable"] is True
    assert report["mqtt_socket_stable"] is True
