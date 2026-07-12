from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .t1_broker_identity_activation_checks import (
    BrokerIdentityActivationCheckError,
    BrokerIdentityActivationHandoffError,
    Runner,
    Verifier,
    runtime_healthy,
    runtime_summary,
    sha256_path,
    validated_handoff,
)
from .t1_broker_identity_activation_handoff import (
    verify_broker_identity_activation_handoff,
)
from .t1_client_migration_audit import (
    ClientMigrationAuditError,
    build_client_migration_audit,
)
from .t1_homeassistant_mqtt_target_gate import (
    HomeAssistantMqttTargetGateError,
    build_homeassistant_mqtt_target_gate,
)
from .t1_shadow import SubprocessRunner

SCHEMA = "gh.m2.t1-broker-identity-preactivation-gate/1"
Builder = Callable[..., dict[str, object]]


def _live_readiness(report: dict[str, object]) -> dict[str, Any]:
    required = {
        "schema": "gh.m2.t1-auth-client-migration-audit/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "audit_complete": True,
        "ready_for_live_apply": False,
    }
    for field, expected in required.items():
        if report.get(field) != expected:
            raise BrokerIdentityActivationCheckError(f"client migration audit failed: {field}")
    live = report.get("live_readiness")
    if not isinstance(live, dict) or live.get("ready") is not True:
        raise BrokerIdentityActivationCheckError("live readiness is not passing")
    broker = live.get("broker")
    gates = live.get("gates")
    if not isinstance(broker, dict) or not isinstance(gates, dict):
        raise BrokerIdentityActivationCheckError("live readiness details are missing")
    required_gates = (
        "anonymous_access_still_enabled",
        "dynamic_security_not_configured",
        "dynamic_security_state_absent",
        "dynamic_security_plugin_available",
        "retained_topic_readable",
        "no_candidate_containers",
    )
    if any(gates.get(field) is not True for field in required_gates):
        raise BrokerIdentityActivationCheckError("live Broker is not in the required preactivation state")
    return live


def _official_reconfigure(
    report: dict[str, object],
    *,
    target_kind: str,
    target_fingerprint: str,
    entry_fingerprint: str,
    storage_sha256: str,
) -> dict[str, Any]:
    required = {
        "schema": "gh.m2.t1-homeassistant-mqtt-target-gate/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "target_model_ready": True,
        "ready_for_operator_reconfigure": False,
        "ready_for_live_apply": False,
    }
    for field, expected in required.items():
        if report.get(field) != expected:
            raise BrokerIdentityActivationCheckError(f"Home Assistant target gate failed: {field}")
    if (
        report.get("selected_target_kind") != target_kind
        or report.get("selected_target_fingerprint") != target_fingerprint
    ):
        raise BrokerIdentityActivationCheckError("Home Assistant target binding drifted")
    official = report.get("homeassistant_official_reconfigure")
    if not isinstance(official, dict):
        raise BrokerIdentityActivationCheckError("Home Assistant official reconfigure details are missing")
    if (
        official.get("pre_change_entry_fingerprint") != entry_fingerprint
        or official.get("pre_change_storage_sha256") != storage_sha256
    ):
        raise BrokerIdentityActivationCheckError("Home Assistant config-entry binding drifted")
    return official


def build_broker_identity_preactivation_gate(
    handoff_directory: str | Path,
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    expected_target_fingerprint: str,
    expected_entry_fingerprint: str,
    expected_storage_sha256: str,
    expected_target_kind: str = "loopback",
    compose_directory: str | Path = "/opt/HomeAssistant/infra/compose/t1",
    secret_root: str | Path = "/opt/greenhouse-secrets/mqtt",
    runner: Runner | None = None,
    handoff_verifier: Verifier = verify_broker_identity_activation_handoff,
    audit_builder: Builder = build_client_migration_audit,
    target_builder: Builder = build_homeassistant_mqtt_target_gate,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    command_runner = runner or SubprocessRunner()
    handoff_root = Path(handoff_directory).expanduser().resolve()
    stage_root = Path(stage_directory).expanduser().resolve()
    manifest, plan = validated_handoff(handoff_root, handoff_verifier)
    stage = manifest.get("stage")
    if not isinstance(stage, dict):
        raise BrokerIdentityActivationCheckError("handoff stage binding is missing")
    if stage.get("name") != stage_root.name or stage.get("manifest_sha256") != sha256_path(
        stage_root / "stage-manifest.json"
    ):
        raise BrokerIdentityActivationCheckError("migration stage binding drifted")

    audit = audit_builder(
        stage_root,
        expected_retained_topic=expected_retained_topic,
        expected_broker="__m2_target_not_selected__",
        compose_directory=compose_directory,
        secret_root=secret_root,
        runner=command_runner,
    )
    live = _live_readiness(audit)
    broker = live["broker"]
    live_sha = broker.get("live_config_sha256")
    if live_sha != stage.get("broker_config_sha256") or live_sha != plan.get("live_broker_config_sha256"):
        raise BrokerIdentityActivationCheckError("live Broker config binding drifted")

    target = target_builder(
        stage_root,
        expected_retained_topic=expected_retained_topic,
        compose_directory=compose_directory,
        secret_root=secret_root,
        runner=command_runner,
    )
    official = _official_reconfigure(
        target,
        target_kind=expected_target_kind,
        target_fingerprint=expected_target_fingerprint,
        entry_fingerprint=expected_entry_fingerprint,
        storage_sha256=expected_storage_sha256,
    )
    runtime = runtime_summary(command_runner)
    if not runtime_healthy(runtime):
        raise BrokerIdentityActivationCheckError("required service runtime is not healthy")
    checks = {
        "handoff_verified": True,
        "stage_binding_unchanged": True,
        "fresh_rollback_verified": True,
        "live_config_binding_unchanged": True,
        "anonymous_compatibility_present": True,
        "dynamic_security_not_active": True,
        "retained_baseline_readable": True,
        "homeassistant_loopback_target_bound": True,
        "homeassistant_entry_binding_unchanged": True,
        "services_running_zero_restart": True,
    }
    return {
        "schema": SCHEMA,
        "read_only": True,
        "preconditions_ready": all(checks.values()),
        "checks": checks,
        "target_kind": expected_target_kind,
        "target_fingerprint": expected_target_fingerprint,
        "entry_fingerprint": official.get("pre_change_entry_fingerprint"),
        "storage_sha256": official.get("pre_change_storage_sha256"),
        "runtime": runtime,
        "activation_blockers": [
            "broker_identity_not_activated",
            "explicit_operator_authorization_required",
            "live_activation_not_executed",
        ],
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Runner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Build a disabled real-T1 Broker identity preactivation gate."
    )
    parser.add_argument("handoff_directory")
    parser.add_argument("stage_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--expected-target-fingerprint", required=True)
    parser.add_argument("--expected-entry-fingerprint", required=True)
    parser.add_argument("--expected-storage-sha256", required=True)
    parser.add_argument("--expected-target-kind", default="loopback")
    args = parser.parse_args(argv)
    try:
        report = build_broker_identity_preactivation_gate(
            args.handoff_directory,
            args.stage_directory,
            expected_retained_topic=args.expected_retained_topic,
            expected_target_fingerprint=args.expected_target_fingerprint,
            expected_entry_fingerprint=args.expected_entry_fingerprint,
            expected_storage_sha256=args.expected_storage_sha256,
            expected_target_kind=args.expected_target_kind,
            runner=runner,
            handoff_verifier=verify_broker_identity_activation_handoff,
        )
    except (
        BrokerIdentityActivationCheckError,
        BrokerIdentityActivationHandoffError,
        ClientMigrationAuditError,
        HomeAssistantMqttTargetGateError,
        OSError,
        ValueError,
    ) as error:
        print(f"T1 Broker identity preactivation gate failed: {error}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if report["preconditions_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
