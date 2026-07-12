from __future__ import annotations

import json
from typing import Any

import pytest

import greenhouse_manager.t1_homeassistant_mqtt_target_gate as gate
from greenhouse_manager.t1_homeassistant_mqtt_target_gate import (
    BrokerCandidate,
    HomeAssistantMqttTargetGateError,
    build_homeassistant_mqtt_target_gate,
)


class FakeRunner:
    def __init__(
        self,
        *,
        homeassistant_mode: str,
        broker_mode: str,
        shared_network: bool,
        aliases: list[str] | None = None,
        probes: dict[str, tuple[bool, bool, int]] | None = None,
        containers: list[dict[str, str]] | None = None,
    ) -> None:
        self.homeassistant_mode = homeassistant_mode
        self.broker_mode = broker_mode
        self.shared_network = shared_network
        self.aliases = aliases or []
        self.probes = probes or {}
        self.containers = containers or [
            {
                "Names": "homeassistant",
                "Image": "homeassistant/home-assistant:stable",
            },
            {
                "Names": "mosquitto",
                "Image": "eclipse-mosquitto:latest",
            },
        ]
        self.commands: list[tuple[str, ...]] = []

    def _inspect(self, name: str) -> dict[str, Any]:
        if self.shared_network:
            networks: dict[str, Any] = {
                "ha_default": {
                    "Aliases": self.aliases if name == "mosquitto" else [name]
                }
            }
        else:
            networks = {
                f"{name}_default": {
                    "Aliases": self.aliases if name == "mosquitto" else [name]
                }
            }
        mode = (
            self.homeassistant_mode if name == "homeassistant" else self.broker_mode
        )
        return {
            "HostConfig": {"NetworkMode": mode},
            "NetworkSettings": {"Networks": networks},
        }

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command == ("docker", "ps", "-a", "--format", "{{json .}}"):
            return (
                0,
                "\n".join(json.dumps(item) for item in self.containers),
            )
        if command[:2] == ("docker", "inspect"):
            return 0, json.dumps([self._inspect(command[2])])
        if command == (
            "docker",
            "exec",
            "homeassistant",
            "sha256sum",
            "/config/.storage/core.config_entries",
        ):
            return 0, f"{'a' * 64}  /config/.storage/core.config_entries\n"
        if command[:5] == (
            "docker",
            "exec",
            "homeassistant",
            "python3",
            "-c",
        ):
            host = command[-2]
            dns_resolved, tcp_connectable, address_count = self.probes.get(
                host,
                (False, False, 0),
            )
            return (
                0,
                json.dumps(
                    {
                        "dns_resolved": dns_resolved,
                        "tcp_connectable": tcp_connectable,
                        "address_count": address_count,
                    }
                ),
            )
        return 1, "unexpected command"


def _prior_audit() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-auth-client-migration-audit/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "audit_complete": True,
        "ready_for_live_apply": False,
        "live_readiness": {"retained_topic_readable": True},
        "homeassistant": {
            "runtime": {"name": "homeassistant"},
            "mqtt_config_entry": {
                "entry_id_fingerprint": "1234567890abcdef",
                "discovery_disabled": False,
            },
            "staged_material": {"staged_material_complete": True},
        },
    }


def _patch_prior(
    monkeypatch: pytest.MonkeyPatch,
    report: dict[str, object] | None = None,
) -> None:
    monkeypatch.setattr(
        gate,
        "build_client_migration_audit",
        lambda *_args, **_kwargs: report or _prior_audit(),
    )


def test_host_network_selects_reachable_loopback_without_exposing_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prior(monkeypatch)
    runner = FakeRunner(
        homeassistant_mode="host",
        broker_mode="host",
        shared_network=False,
        probes={
            "mosquitto": (False, False, 0),
            "127.0.0.1": (True, True, 1),
        },
    )

    report = build_homeassistant_mqtt_target_gate(
        "/private/stage",
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=runner,
    )

    assert report["target_model_ready"] is True
    assert report["selected_target_kind"] == "loopback"
    assert report["ready_for_operator_reconfigure"] is False
    assert report["homeassistant_official_reconfigure"][
        "operator_action_authorized"
    ] is False
    assert "broker_identity_not_activated" in report["activation_blockers"]
    serialized = json.dumps(report)
    assert "127.0.0.1" not in serialized
    assert "mosquitto" not in serialized


def test_shared_user_defined_network_selects_declared_service_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prior(monkeypatch)
    runner = FakeRunner(
        homeassistant_mode="ha_default",
        broker_mode="ha_default",
        shared_network=True,
        aliases=["mosquitto", "broker-container-id"],
        probes={
            "mosquitto": (True, True, 1),
            "127.0.0.1": (True, False, 1),
        },
    )

    report = build_homeassistant_mqtt_target_gate(
        "/private/stage",
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=runner,
    )

    assert report["target_model_ready"] is True
    assert report["selected_target_kind"] == "docker_service_alias"
    assert report["network_topology"]["shared_network_count"] == 1
    alias_result = next(
        item
        for item in report["candidates"]
        if item["kind"] == "docker_service_alias"
    )
    assert alias_result["declared_on_shared_network"] is True
    assert alias_result["eligible"] is True


def test_host_address_requires_explicit_fallback_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prior(monkeypatch)
    candidate = BrokerCandidate("t1_host", "host_address", "192.0.2.10")
    runner = FakeRunner(
        homeassistant_mode="bridge",
        broker_mode="bridge",
        shared_network=False,
        probes={"192.0.2.10": (True, True, 1)},
    )

    blocked = build_homeassistant_mqtt_target_gate(
        "/private/stage",
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        candidates=(candidate,),
        runner=runner,
    )
    assert blocked["target_model_ready"] is False
    assert "homeassistant_broker_target_unresolved" in blocked[
        "activation_blockers"
    ]

    allowed = build_homeassistant_mqtt_target_gate(
        "/private/stage",
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        candidates=(candidate,),
        allow_host_address_fallback=True,
        runner=runner,
    )
    assert allowed["target_model_ready"] is True
    assert allowed["selected_target_kind"] == "host_address"
    assert "192.0.2.10" not in json.dumps(allowed)


def test_gate_rejects_unsafe_or_incomplete_prior_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unsafe = _prior_audit()
    unsafe["apply_enabled"] = True
    _patch_prior(monkeypatch, unsafe)
    runner = FakeRunner(
        homeassistant_mode="host",
        broker_mode="host",
        shared_network=False,
    )

    with pytest.raises(HomeAssistantMqttTargetGateError, match="safe completed"):
        build_homeassistant_mqtt_target_gate(
            "/private/stage",
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            runner=runner,
        )


def test_candidate_kinds_and_labels_must_be_unique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prior(monkeypatch)
    candidates = (
        BrokerCandidate("one", "loopback", "127.0.0.1"),
        BrokerCandidate("two", "loopback", "localhost"),
    )

    with pytest.raises(ValueError, match="unique"):
        build_homeassistant_mqtt_target_gate(
            "/private/stage",
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            candidates=candidates,
            runner=FakeRunner(
                homeassistant_mode="host",
                broker_mode="host",
                shared_network=False,
            ),
        )


def test_gate_rejects_ambiguous_broker_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prior(monkeypatch)
    runner = FakeRunner(
        homeassistant_mode="host",
        broker_mode="host",
        shared_network=False,
        containers=[
            {
                "Names": "homeassistant",
                "Image": "homeassistant/home-assistant:stable",
            },
            {"Names": "mosquitto", "Image": "eclipse-mosquitto:latest"},
            {"Names": "mosquitto-old", "Image": "eclipse-mosquitto:latest"},
        ],
    )

    with pytest.raises(HomeAssistantMqttTargetGateError, match="exactly one mosquitto"):
        build_homeassistant_mqtt_target_gate(
            "/private/stage",
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            runner=runner,
        )


def test_gate_executes_only_inventory_inspect_fingerprint_and_tcp_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prior(monkeypatch)
    runner = FakeRunner(
        homeassistant_mode="host",
        broker_mode="host",
        shared_network=False,
        probes={
            "mosquitto": (False, False, 0),
            "127.0.0.1": (True, True, 1),
        },
    )

    build_homeassistant_mqtt_target_gate(
        "/private/stage",
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=runner,
    )

    serialized_commands = "\n".join(" ".join(command) for command in runner.commands)
    for forbidden in (
        "docker restart",
        "docker stop",
        "docker start",
        "docker compose",
        "rm ",
        "mv ",
        "cp ",
        "chmod ",
        "core.config_entries >",
    ):
        assert forbidden not in serialized_commands
