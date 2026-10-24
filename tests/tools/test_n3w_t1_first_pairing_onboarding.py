from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_first_pairing_onboarding.py"


def load_tool():
    name = "n3w_t1_first_pairing_onboarding"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def factory_compose(tool, *, pairing: str = "false", broker_host: str | None = None):
    return {
        "services": {
            "broker": {},
            "manager": {
                "network_mode": "host",
                "profiles": ["application"],
                "environment": {
                    "GH_N3W_RUNTIME_ENABLED": "true",
                    "GH_N3W_PRODUCT_PAIRING_ENABLED": pairing,
                    "GH_N3W_PAIRING_ADVERTISED_HOST": "auto",
                    "GH_N3W_NODE_BROKER_HOST": (
                        broker_host
                        if broker_host is not None
                        else tool.FACTORY_BROKER_PLACEHOLDER
                    ),
                    "GH_N3W_NODE_BROKER_PORT": "8883",
                    "GH_N3W_NODE_BROKER_TLS_SERVER_NAME": "armbian",
                },
            },
            "homeassistant": {},
        }
    }


def snapshot(
    *,
    manager_id: str = "manager-a",
    broker_id: str = "broker-a",
    ha_id: str = "ha-a",
    pairing: str = "false",
    broker_host: str = "gate-f-unbound.invalid",
):
    return {
        "broker": {
            "id": broker_id,
            "id_sha256": "b" * 64,
            "restart_count": 0,
            "network_mode": "n3wfc4-private",
            "env": {},
        },
        "manager": {
            "id": manager_id,
            "id_sha256": "m" * 64,
            "restart_count": 0,
            "network_mode": "host",
            "env": {
                "GH_N3W_RUNTIME_ENABLED": "true",
                "GH_N3W_PRODUCT_PAIRING_ENABLED": pairing,
                "GH_N3W_PAIRING_ADVERTISED_HOST": "auto",
                "GH_N3W_NODE_BROKER_HOST": broker_host,
                "GH_N3W_NODE_BROKER_TLS_SERVER_NAME": "armbian",
            },
        },
        "homeassistant": {
            "id": ha_id,
            "id_sha256": "h" * 64,
            "restart_count": 0,
            "network_mode": "host",
            "env": {},
        },
    }


def zero_counts():
    return {
        "registrations": 0,
        "pairing_sessions": 0,
        "registration_events": 0,
        "node_id_leases": 0,
    }


def paired_counts():
    return {
        "registrations": 1,
        "pairing_sessions": 1,
        "registration_events": 2,
        "node_id_leases": 1,
    }


def zero_security_counts():
    return {
        "credential_assignments": 0,
        "application_key_active_nodes": 0,
        "application_key_epochs": 0,
    }


def paired_security_counts():
    return {
        "credential_assignments": 1,
        "application_key_active_nodes": 1,
        "application_key_epochs": 1,
    }


def test_command_surface_and_factory_defaults_are_fail_closed() -> None:
    tool = load_tool()
    source = TOOL.read_text(encoding="utf-8")

    assert source.startswith("#!/usr/bin/python3\n")
    assert tool.OPEN_CONFIRMATION == "OPEN FIRST PAIRING WINDOW: YES"
    assert tool.CLOSE_CONFIRMATION == "CLOSE FIRST PAIRING WINDOW: YES"
    assert tool.FACTORY_BROKER_PLACEHOLDER == "gate-f-unbound.invalid"
    assert 'subparsers.add_parser("inspect")' in source
    assert 'subparsers.add_parser("open")' in source
    assert 'subparsers.add_parser("close")' in source
    assert "--force-recreate" in source
    assert "--no-deps" in source
    assert '"manager"' in source
    assert "docker system prune" not in source
    assert "docker compose down" not in source


def test_factory_compose_requires_disabled_pairing_and_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()

    monkeypatch.setattr(tool, "_render_compose", lambda **_kwargs: factory_compose(tool))
    tool._validate_factory_compose()

    monkeypatch.setattr(
        tool,
        "_render_compose",
        lambda **_kwargs: factory_compose(tool, pairing="true"),
    )
    with pytest.raises(tool.OnboardingError, match="GH_N3W_PRODUCT_PAIRING_ENABLED"):
        tool._validate_factory_compose()

    monkeypatch.setattr(
        tool,
        "_render_compose",
        lambda **_kwargs: factory_compose(tool, broker_host="192.168.1.10"),
    )
    with pytest.raises(tool.OnboardingError, match="GH_N3W_NODE_BROKER_HOST"):
        tool._validate_factory_compose()


def test_override_compose_changes_only_pairing_locator_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    host = "192.168.1.10"
    monkeypatch.setattr(
        tool,
        "_render_compose",
        lambda **_kwargs: factory_compose(
            tool,
            pairing="true",
            broker_host=host,
        ),
    )

    tool._validate_override_compose(host)

    with pytest.raises(tool.OnboardingError, match="onboarding_broker_host_mismatch"):
        tool._validate_override_compose("192.168.1.11")


def test_manager_recreate_is_scoped_to_manager_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(
        tool,
        "_run",
        lambda argv, **_kwargs: calls.append(tuple(argv)) or "",
    )

    tool._recreate_manager(override=True)
    tool._recreate_manager(override=False)

    assert len(calls) == 2
    for argv in calls:
        assert argv[-5:] == (
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "manager",
        )
        assert "broker" not in argv[-5:]
        assert "homeassistant" not in argv[-5:]
    assert str(tool.OVERRIDE_PATH) in calls[0]
    assert str(tool.OVERRIDE_PATH) not in calls[1]


def test_route_selected_broker_uses_exact_manager_runtime_logic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    calls: list[tuple[str, ...]] = []

    def fake_run(argv, **_kwargs):
        calls.append(tuple(argv))
        return json.dumps({"local": True, "selected": "192.168.68.126"})

    monkeypatch.setattr(tool, "_run", fake_run)

    result = tool._resolve_route_selected_broker(
        "manager-id",
        "192.168.68.50",
    )

    assert result == "192.168.68.126"
    assert calls[0][:3] == ("docker", "exec", "manager-id")
    assert "resolve_route_selected_ipv4" in calls[0][5]


def test_route_selected_broker_rejects_nonlocal_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()

    monkeypatch.setattr(
        tool,
        "_run",
        lambda *_args, **_kwargs: json.dumps(
            {"local": False, "selected": ""}
        ),
    )

    with pytest.raises(tool.OnboardingError, match="peer_not_local"):
        tool._resolve_route_selected_broker(
            "manager-id",
            "192.168.68.50",
        )


def test_first_pair_state_requires_all_registration_tables_empty() -> None:
    tool = load_tool()

    tool._require_clean_first_pair_state(
        zero_counts(),
        zero_security_counts(),
    )

    current = zero_counts()
    current["pairing_sessions"] = 1
    with pytest.raises(tool.OnboardingError, match="first_pair_state_not_clean"):
        tool._require_clean_first_pair_state(
            current,
            zero_security_counts(),
        )

    security = zero_security_counts()
    security["credential_assignments"] = 1
    with pytest.raises(
        tool.OnboardingError,
        match="first_pair_security_state_not_clean",
    ):
        tool._require_clean_first_pair_state(
            zero_counts(),
            security,
        )


def test_open_claims_before_manager_recreate_and_never_outputs_locator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    baseline = snapshot()
    after = snapshot(
        manager_id="manager-b",
        pairing="true",
        broker_host="192.168.68.126",
    )
    runtime_values = iter((baseline, after))
    events: list[str] = []

    monkeypatch.setattr(tool, "_require_file", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tool, "_validate_factory_compose", lambda: {})
    monkeypatch.setattr(
        tool,
        "_validate_factory_marker",
        lambda: {
            "release_id": "r",
            "host_instance_id": "h",
            "system_id": "s",
        },
    )
    monkeypatch.setattr(tool, "_runtime_snapshot", lambda: next(runtime_values))
    monkeypatch.setattr(tool, "_validate_factory_runtime", lambda _value: None)
    monkeypatch.setattr(tool, "_db_counts", zero_counts)
    monkeypatch.setattr(tool, "_security_state_counts", zero_security_counts)
    monkeypatch.setattr(tool, "_listener_count", lambda *_args: 0)
    monkeypatch.setattr(
        tool,
        "_resolve_route_selected_broker",
        lambda *_args: "192.168.68.126",
    )
    monkeypatch.setattr(tool, "_probe_external_broker_tls", lambda _host: None)

    def claim(**_kwargs):
        events.append("claim")
        return {
            "broker_host_sha256": tool._sha256_text("192.168.68.126")
        }

    monkeypatch.setattr(tool, "_claim_transaction", claim)
    monkeypatch.setattr(
        tool,
        "_write_override",
        lambda _host: events.append("override"),
    )
    monkeypatch.setattr(tool, "_validate_override_compose", lambda _host: {})
    monkeypatch.setattr(
        tool,
        "_recreate_manager",
        lambda **kwargs: events.append(
            f"recreate:{kwargs['override']}"
        ),
    )
    monkeypatch.setattr(
        tool,
        "_wait_onboarding_ready",
        lambda _host: after["manager"],
    )
    monkeypatch.setattr(
        tool,
        "_validate_non_manager_continuity",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda **fields: {
            **fields,
            "broker_host_sha256": tool._sha256_text(
                "192.168.68.126"
            ),
        },
    )

    report = tool.open_window(
        authorization_id="N3W_T1_FIRST_PAIRING_TEST_01",
        peer_ip="192.168.68.50",
        confirmation=tool.OPEN_CONFIRMATION,
        window_seconds=180,
    )

    assert events.index("claim") < events.index("recreate:True")
    assert report["status"] == "PASS"
    assert report["raw_locator_in_output"] is False
    assert "192.168.68.126" not in json.dumps(report)


def test_open_failure_after_recreate_restores_factory_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    baseline = snapshot()
    restored = snapshot(manager_id="manager-c")
    runtime_values = iter((baseline, restored))
    recreate: list[bool] = []
    advanced: list[dict[str, object]] = []

    monkeypatch.setattr(tool, "_require_file", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tool, "_validate_factory_compose", lambda: {})
    monkeypatch.setattr(
        tool,
        "_validate_factory_marker",
        lambda: {
            "release_id": "r",
            "host_instance_id": "h",
            "system_id": "s",
        },
    )
    monkeypatch.setattr(tool, "_runtime_snapshot", lambda: next(runtime_values))
    monkeypatch.setattr(tool, "_validate_factory_runtime", lambda _value: None)
    monkeypatch.setattr(tool, "_db_counts", zero_counts)
    monkeypatch.setattr(tool, "_security_state_counts", zero_security_counts)
    monkeypatch.setattr(tool, "_listener_count", lambda *_args: 0)
    monkeypatch.setattr(
        tool,
        "_resolve_route_selected_broker",
        lambda *_args: "192.168.68.126",
    )
    monkeypatch.setattr(tool, "_probe_external_broker_tls", lambda _host: None)
    monkeypatch.setattr(
        tool,
        "_claim_transaction",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(tool, "_write_override", lambda _host: None)
    monkeypatch.setattr(tool, "_validate_override_compose", lambda _host: {})
    monkeypatch.setattr(
        tool,
        "_recreate_manager",
        lambda **kwargs: recreate.append(kwargs["override"]),
    )
    monkeypatch.setattr(
        tool,
        "_wait_onboarding_ready",
        lambda _host: (_ for _ in ()).throw(
            tool.OnboardingError("not-ready")
        ),
    )
    monkeypatch.setattr(tool, "_remove_override", lambda: None)
    monkeypatch.setattr(
        tool,
        "_wait_factory_ready",
        lambda: restored["manager"],
    )
    monkeypatch.setattr(
        tool,
        "_validate_non_manager_continuity",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda **fields: advanced.append(fields) or fields,
    )

    with pytest.raises(
        tool.OnboardingError,
        match="open_failed:OnboardingError:rollback_PASS",
    ):
        tool.open_window(
            authorization_id="N3W_T1_FIRST_PAIRING_TEST_02",
            peer_ip="192.168.68.50",
            confirmation=tool.OPEN_CONFIRMATION,
            window_seconds=180,
        )

    assert recreate == [True, False]
    assert advanced[-1]["status"] == "STOPPED_OPEN_FAILED"
    assert advanced[-1]["rollback_status"] == "PASS"


def test_close_success_requires_pairing_evidence_and_restores_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    before = snapshot(
        manager_id="manager-open",
        pairing="true",
        broker_host="192.168.68.126",
    )
    after = snapshot(manager_id="manager-closed")
    runtime_values = iter((before, after))
    counts = paired_counts()
    recreated: list[bool] = []
    advanced: list[dict[str, object]] = []

    transaction = {
        "schema": tool.TRANSACTION_SCHEMA,
        "status": "OPEN",
        "authorization_id": "N3W_T1_FIRST_PAIRING_TEST_03",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "broker_host": "192.168.68.126",
        "expires_at_unix": int(time.time()) + 120,
        "manager_recreate_count": 1,
        "baseline_container_ids": {
            "broker": "broker-a",
            "manager": "manager-a",
            "homeassistant": "ha-a",
        },
    }

    monkeypatch.setattr(tool, "_transaction", lambda: transaction)
    monkeypatch.setattr(tool, "_runtime_snapshot", lambda: next(runtime_values))
    monkeypatch.setattr(tool, "_db_counts", lambda: dict(counts))
    monkeypatch.setattr(
        tool,
        "_security_state_counts",
        lambda: paired_security_counts(),
    )
    monkeypatch.setattr(
        tool,
        "_first_pair_success_evidence",
        lambda: {
            "database_counts": dict(counts),
            "security_counts": paired_security_counts(),
            "hardware_id_sha256": "a" * 64,
            "pairing_id_sha256": "b" * 64,
            "node_id_sha256": "c" * 64,
            "credential_generation": 1,
            "application_key_epoch": 1,
        },
    )
    monkeypatch.setattr(
        tool,
        "_recreate_manager",
        lambda **kwargs: recreated.append(kwargs["override"]),
    )
    monkeypatch.setattr(tool, "_remove_override", lambda: None)
    monkeypatch.setattr(
        tool,
        "_wait_factory_ready",
        lambda: after["manager"],
    )
    monkeypatch.setattr(
        tool,
        "_validate_non_manager_continuity",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        tool,
        "_advance_transaction",
        lambda **fields: advanced.append(fields) or fields,
    )

    report = tool.close_window(
        authorization_id="N3W_T1_FIRST_PAIRING_TEST_03",
        confirmation=tool.CLOSE_CONFIRMATION,
        outcome="success",
    )

    assert recreated == [False]
    assert report["status"] == "PASS"
    assert report["pairing_window_state"] == "CLOSED_PASS"
    assert report["factory_pairing_disabled"] is True
    assert report["factory_broker_placeholder_restored"] is True
    assert advanced[-1]["status"] == "CLOSED_PASS"


def test_close_success_rejects_missing_registration_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    before = snapshot(
        manager_id="manager-open",
        pairing="true",
        broker_host="192.168.68.126",
    )
    transaction = {
        "schema": tool.TRANSACTION_SCHEMA,
        "status": "OPEN",
        "authorization_id": "N3W_T1_FIRST_PAIRING_TEST_04",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "broker_host": "192.168.68.126",
        "expires_at_unix": int(time.time()) + 120,
        "manager_recreate_count": 1,
        "baseline_container_ids": {
            "broker": "broker-a",
            "manager": "manager-a",
            "homeassistant": "ha-a",
        },
    }

    monkeypatch.setattr(tool, "_transaction", lambda: transaction)
    monkeypatch.setattr(tool, "_runtime_snapshot", lambda: before)
    monkeypatch.setattr(
        tool,
        "_first_pair_success_evidence",
        lambda: (_ for _ in ()).throw(
            tool.OnboardingError("first_pair_success_state_not_observed")
        ),
    )

    with pytest.raises(
        tool.OnboardingError,
        match="first_pair_success_state_not_observed",
    ):
        tool.close_window(
            authorization_id="N3W_T1_FIRST_PAIRING_TEST_04",
            confirmation=tool.CLOSE_CONFIRMATION,
            outcome="success",
        )


def test_authorization_is_one_shot_and_strictly_named() -> None:
    tool = load_tool()

    assert (
        tool._authorization_id("N3W_T1_FIRST_PAIRING_BOARD_D_20261024_01")
        == "N3W_T1_FIRST_PAIRING_BOARD_D_20261024_01"
    )

    with pytest.raises(tool.OnboardingError, match="authorization_id_invalid"):
        tool._authorization_id("anything")
