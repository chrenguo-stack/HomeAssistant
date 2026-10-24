from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = (
    ROOT
    / "tools"
    / "n3w_t1_first_pairing_onboarding.py"
)

TEST_PEER_IP = str(
    ipaddress.IPv4Address(
        0xC0A83228
    )
)
TEST_BROKER_IP = str(
    ipaddress.IPv4Address(
        0xC0A83201
    )
)


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_first_pairing_onboarding",
        TOOL,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(
        spec
    )
    spec.loader.exec_module(module)
    return module


def _private_root(
    tmp_path: Path,
) -> Path:
    root = tmp_path / "provisioning"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return root


def _runtime_snapshot(
    *,
    manager_id: str = "b" * 64,
    manager_restart: int = 0,
    broker_id: str = "a" * 64,
    broker_restart: int = 0,
    ha_id: str = "c" * 64,
    ha_restart: int = 0,
):
    return {
        "broker": {
            "id": broker_id,
            "id_sha256": "1" * 64,
            "restart_count": broker_restart,
            "network_mode": "bridge",
            "env": {},
        },
        "manager": {
            "id": manager_id,
            "id_sha256": "2" * 64,
            "restart_count": manager_restart,
            "network_mode": "host",
            "env": {
                "GH_N3W_RUNTIME_ENABLED": "true",
                "GH_N3W_PRODUCT_PAIRING_ENABLED": "false",
                "GH_N3W_PAIRING_ADVERTISED_HOST": "auto",
                "GH_N3W_NODE_BROKER_HOST": (
                    "gate-f-unbound.invalid"
                ),
                "GH_N3W_NODE_BROKER_TLS_SERVER_NAME": (
                    "armbian"
                ),
            },
        },
        "homeassistant": {
            "id": ha_id,
            "id_sha256": "3" * 64,
            "restart_count": ha_restart,
            "network_mode": "bridge",
            "env": {},
        },
    }


def _factory():
    return {
        "schema": "gh.n3w.t1-factory-accepted/1",
        "status": "PASS",
        "factory_accepted": True,
        "release_id": "release-test",
        "host_instance_id": "host-test",
        "system_id": "greenhouse",
    }


def _zero_counts():
    return {
        "registrations": 0,
        "pairing_sessions": 0,
        "registration_events": 0,
        "node_id_leases": 0,
    }


def _zero_security_counts():
    return {
        "credential_records": 0,
        "application_key_records": 0,
        "application_key_files": 0,
        "peer_trust_records": 0,
    }


def _paired_counts():
    return {
        "registrations": 1,
        "pairing_sessions": 1,
        "registration_events": 1,
        "node_id_leases": 1,
    }


def _paired_security_counts():
    return {
        "credential_records": 1,
        "application_key_records": 1,
        "application_key_files": 1,
        "peer_trust_records": 1,
    }


def _configure_transaction_paths(
    tool,
    tmp_path: Path,
) -> Path:
    root = _private_root(tmp_path)
    tool.PROVISIONING_ROOT = root
    tool.TRANSACTION_PATH = (
        root
        / "FIRST_PAIRING_ONBOARDING.json"
    )
    tool.RUNTIME_ROOT = (
        tmp_path
        / "runtime"
    )
    tool.WATCHDOG_TOOL_PATH = (
        tool.RUNTIME_ROOT
        / "onboarding-watchdog.py"
    )
    return root


def _claim(
    tool,
    *,
    window_seconds: int = 300,
):
    baseline = _runtime_snapshot()
    return tool._claim_transaction(
        authorization_id=(
            "N3W_T1_FIRST_PAIRING_TEST_01"
        ),
        factory=_factory(),
        peer_ip=TEST_PEER_IP,
        broker_host=TEST_BROKER_IP,
        baseline=baseline,
        window_seconds=window_seconds,
    )


def _open_transaction(
    tool,
    *,
    window_seconds: int = 300,
):
    document = _claim(
        tool,
        window_seconds=window_seconds,
    )
    opened_at = int(time.time())
    return tool._advance_transaction(
        status="OPEN",
        opened_at_unix=opened_at,
        expires_at_unix=(
            opened_at
            + window_seconds
        ),
        watchdog_unit=(
            tool._watchdog_unit_name(
                document[
                    "authorization_id"
                ]
            )
        ),
        watchdog_armed=True,
        watchdog_authorization_sha256=(
            tool._sha256_text(
                document[
                    "authorization_id"
                ]
            )
        ),
        watchdog_tool_sha256=(
            document["tool_sha256"]
        ),
    )


def test_source_removes_manager_recreate_normal_path() -> None:
    source = TOOL.read_text(
        encoding="utf-8"
    )

    assert "--force-recreate" not in source
    assert "manager-pairing.override" not in source
    assert "_recreate_manager" not in source
    assert "_restore_factory_manager" not in source
    assert (
        "greenhouse-manager-pairing"
        in source
    )
    assert 'f"window-{command}"' in source
    assert '"greenhouse-manager-pairing"' in source


def test_command_surface_and_factory_defaults_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "_require_root",
        lambda: None,
    )
    parser = tool._parser()

    open_args = parser.parse_args(
        [
            "open",
            "--authorization-id",
            (
                "N3W_T1_FIRST_PAIRING_TEST_01"
            ),
            "--peer-ip",
            TEST_PEER_IP,
            "--confirm",
            tool.OPEN_CONFIRMATION,
        ]
    )
    assert open_args.window_seconds == 300

    with pytest.raises(
        tool.OnboardingError,
        match="window_seconds_invalid",
    ):
        tool.open_window(
            authorization_id=(
                "N3W_T1_FIRST_PAIRING_TEST_01"
            ),
            peer_ip=TEST_PEER_IP,
            confirmation=(
                tool.OPEN_CONFIRMATION
            ),
            window_seconds=179,
        )


def test_claim_persists_hashes_not_raw_locators(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    _configure_transaction_paths(
        tool,
        tmp_path,
    )

    document = _claim(tool)
    persisted = json.loads(
        tool.TRANSACTION_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert document["schema"].endswith(
        "/2"
    )
    assert (
        persisted["peer_ip_sha256"]
        == tool._sha256_text(
            TEST_PEER_IP
        )
    )
    assert (
        persisted["broker_host_sha256"]
        == tool._sha256_text(
            TEST_BROKER_IP
        )
    )
    assert "peer_ip" not in persisted
    assert "broker_host" not in persisted
    assert TEST_PEER_IP not in json.dumps(
        persisted
    )
    assert TEST_BROKER_IP not in json.dumps(
        persisted
    )
    assert tool._transaction() == persisted


def test_transaction_parser_rejects_raw_locator_in_v2(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    _configure_transaction_paths(
        tool,
        tmp_path,
    )
    document = _claim(tool)
    document["broker_host"] = (
        TEST_BROKER_IP
    )
    tool._write_private_json(
        tool.TRANSACTION_PATH,
        document,
    )

    with pytest.raises(
        tool.OnboardingError,
        match=(
            "onboarding_transaction_raw_locator_forbidden"
        ),
    ):
        tool._transaction()


def test_legacy_consumed_transaction_is_read_only_and_non_replayable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "_require_root",
        lambda: None,
    )
    _configure_transaction_paths(
        tool,
        tmp_path,
    )
    legacy = {
        "schema": (
            tool.LEGACY_TRANSACTION_SCHEMA
        ),
        "status": "OPEN_RESTORE_PENDING",
        "authorization_id": (
            "N3W_T1_FIRST_PAIRING_OLD_01"
        ),
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "broker_host": TEST_BROKER_IP,
    }
    tool._write_private_json(
        tool.TRANSACTION_PATH,
        legacy,
    )

    observed = tool._transaction()

    assert observed["status"] == (
        "OPEN_RESTORE_PENDING"
    )

    with pytest.raises(
        tool.OnboardingError,
        match=(
            "onboarding_transaction_already_exists"
        ),
    ):
        _claim(tool)

    with pytest.raises(
        tool.OnboardingError,
        match=(
            "legacy_transaction_requires_separate_recovery"
        ),
    ):
        tool.expire_window(
            authorization_sha256=(
                tool._sha256_text(
                    legacy[
                        "authorization_id"
                    ]
                )
            )
        )


def test_window_control_uses_local_manager_cli_and_never_returns_locator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    commands: list[
        tuple[str, ...]
    ] = []

    def run(argv, **kwargs):
        commands.append(tuple(argv))
        return json.dumps(
            {
                "schema": (
                    "gh.n3w."
                    "pairing-window-control-result/1"
                ),
                "accepted": True,
                "code": "opened",
                "pairing_window_state": "OPEN",
                "window_seconds": 300,
                "expires_in_seconds": 299,
                "broker_host_sha256": (
                    "d" * 64
                ),
                "close_reason": "open",
                "failure_type": None,
                "raw_locator_in_output": False,
            }
        )

    monkeypatch.setattr(
        tool,
        "_run",
        run,
    )

    result = tool._window_control(
        "b" * 64,
        "open",
        peer_ip=TEST_PEER_IP,
        window_seconds=300,
    )

    assert result["accepted"] is True
    assert commands == [
        (
            "docker",
            "exec",
            "b" * 64,
            "greenhouse-manager-pairing",
            "window-open",
            "--peer-ip",
            TEST_PEER_IP,
            "--window-seconds",
            "300",
        )
    ]
    assert TEST_BROKER_IP not in json.dumps(
        result
    )


def test_open_uses_dynamic_window_and_preserves_all_container_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    _configure_transaction_paths(
        tool,
        tmp_path,
    )
    baseline = _runtime_snapshot()
    calls: list[str] = []

    monkeypatch.setattr(
        tool,
        "_require_root",
        lambda: None,
    )
    monkeypatch.setattr(
        tool,
        "_require_file",
        lambda path, **kwargs: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_compose",
        dict,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_marker",
        _factory,
    )
    monkeypatch.setattr(
        tool,
        "_runtime_snapshot",
        lambda: baseline,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_runtime",
        lambda snapshot: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_runtime_configuration",
        lambda snapshot: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_runtime_continuity",
        lambda before, after: None,
    )
    monkeypatch.setattr(
        tool,
        "_db_counts",
        _zero_counts,
    )
    monkeypatch.setattr(
        tool,
        "_security_state_counts",
        _zero_security_counts,
    )
    monkeypatch.setattr(
        tool,
        "_require_clean_first_pair_state",
        lambda counts, security: None,
    )
    monkeypatch.setattr(
        tool,
        "_resolve_route_selected_broker",
        lambda manager, peer: (
            TEST_BROKER_IP
        ),
    )
    monkeypatch.setattr(
        tool,
        "_probe_external_broker_tls",
        lambda host: None,
    )

    def control(
        manager,
        command,
        **kwargs,
    ):
        calls.append(command)
        return {
            "accepted": True,
            "code": (
                "opened"
                if command == "open"
                else "status"
            ),
            "pairing_window_state": "OPEN",
            "broker_host_sha256": (
                tool._sha256_text(
                    TEST_BROKER_IP
                )
            ),
            "raw_locator_in_output": False,
        }

    monkeypatch.setattr(
        tool,
        "_window_control",
        control,
    )
    monkeypatch.setattr(
        tool,
        "_wait_dynamic_open",
        lambda manager, expected: {},
    )

    def arm(transaction):
        return tool._advance_transaction(
            watchdog_unit=(
                tool._watchdog_unit_name(
                    transaction[
                        "authorization_id"
                    ]
                )
            ),
            watchdog_armed=True,
            watchdog_authorization_sha256=(
                tool._sha256_text(
                    transaction[
                        "authorization_id"
                    ]
                )
            ),
            watchdog_tool_sha256=(
                transaction[
                    "tool_sha256"
                ]
            ),
        )

    monkeypatch.setattr(
        tool,
        "_arm_watchdog",
        arm,
    )
    monkeypatch.setattr(
        tool,
        "_watchdog_is_active",
        lambda transaction: True,
    )

    report = tool.open_window(
        authorization_id=(
            "N3W_T1_FIRST_PAIRING_TEST_01"
        ),
        peer_ip=TEST_PEER_IP,
        confirmation=tool.OPEN_CONFIRMATION,
        window_seconds=300,
    )

    assert report["status"] == "PASS"
    assert report["manager_recreated"] is False
    assert (
        report["manager_container_unchanged"]
        is True
    )
    assert calls == ["open"]
    transaction = tool._transaction()
    assert transaction["status"] == "OPEN"
    assert (
        transaction[
            "broker_host_sha256"
        ]
        == tool._sha256_text(
            TEST_BROKER_IP
        )
    )
    assert "broker_host" not in transaction
    assert "peer_ip" not in transaction


def test_open_failure_closes_dynamic_exposure_without_manager_recreate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    _configure_transaction_paths(
        tool,
        tmp_path,
    )
    baseline = _runtime_snapshot()
    commands: list[str] = []

    monkeypatch.setattr(
        tool,
        "_require_root",
        lambda: None,
    )
    monkeypatch.setattr(
        tool,
        "_require_file",
        lambda path, **kwargs: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_compose",
        dict,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_marker",
        _factory,
    )
    monkeypatch.setattr(
        tool,
        "_runtime_snapshot",
        lambda: baseline,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_runtime",
        lambda snapshot: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_runtime_continuity",
        lambda before, after: None,
    )
    monkeypatch.setattr(
        tool,
        "_db_counts",
        _zero_counts,
    )
    monkeypatch.setattr(
        tool,
        "_security_state_counts",
        _zero_security_counts,
    )
    monkeypatch.setattr(
        tool,
        "_require_clean_first_pair_state",
        lambda counts, security: None,
    )
    monkeypatch.setattr(
        tool,
        "_resolve_route_selected_broker",
        lambda manager, peer: (
            TEST_BROKER_IP
        ),
    )
    monkeypatch.setattr(
        tool,
        "_probe_external_broker_tls",
        lambda host: None,
    )

    def control(
        manager,
        command,
        **kwargs,
    ):
        commands.append(command)
        if command == "open":
            return {
                "accepted": True,
                "code": "opened",
                "pairing_window_state": "OPEN",
                "broker_host_sha256": (
                    tool._sha256_text(
                        TEST_BROKER_IP
                    )
                ),
                "raw_locator_in_output": False,
            }
        return {
            "accepted": True,
            "code": "closed",
            "pairing_window_state": "CLOSED",
            "broker_host_sha256": None,
            "raw_locator_in_output": False,
        }

    monkeypatch.setattr(
        tool,
        "_window_control",
        control,
    )
    monkeypatch.setattr(
        tool,
        "_wait_dynamic_open",
        lambda manager, expected: (
            (_ for _ in ()).throw(
                tool.OnboardingError(
                    "health_failed"
                )
            )
        ),
    )
    monkeypatch.setattr(
        tool,
        "_wait_dynamic_closed",
        lambda manager: {},
    )

    with pytest.raises(
        tool.OnboardingError,
        match="dynamic_close_PASS",
    ):
        tool.open_window(
            authorization_id=(
                "N3W_T1_FIRST_PAIRING_TEST_01"
            ),
            peer_ip=TEST_PEER_IP,
            confirmation=(
                tool.OPEN_CONFIRMATION
            ),
            window_seconds=300,
        )

    transaction = tool._transaction()
    assert (
        transaction["status"]
        == "STOPPED_OPEN_FAILED"
    )
    assert (
        transaction[
            "pairing_exposure_closed"
        ]
        is True
    )
    assert commands == [
        "open",
        "close",
    ]


def test_close_success_uses_durable_pairing_evidence_and_no_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    _configure_transaction_paths(
        tool,
        tmp_path,
    )
    transaction = _open_transaction(
        tool
    )
    baseline = _runtime_snapshot()
    evidence = {
        "database_counts": (
            _paired_counts()
        ),
        "security_counts": (
            _paired_security_counts()
        ),
        "hardware_id_sha256": "1" * 64,
        "pairing_id_sha256": "2" * 64,
        "node_id_sha256": "3" * 64,
        "credential_generation": 1,
        "application_key_epoch": 1,
        "peer_trust_generation": 1,
        "peer_trust_system_id_sha256": (
            "4" * 64
        ),
    }

    monkeypatch.setattr(
        tool,
        "_require_root",
        lambda: None,
    )
    monkeypatch.setattr(
        tool,
        "_runtime_snapshot",
        lambda: baseline,
    )
    monkeypatch.setattr(
        tool,
        "_validate_runtime_continuity",
        lambda before, after: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_runtime_configuration",
        lambda snapshot: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_runtime",
        lambda snapshot: None,
    )

    states = iter(
        [
            {
                "accepted": True,
                "code": "status",
                "pairing_window_state": "OPEN",
                "broker_host_sha256": (
                    transaction[
                        "broker_host_sha256"
                    ]
                ),
                "raw_locator_in_output": False,
            },
            {
                "accepted": True,
                "code": "closed",
                "pairing_window_state": "CLOSED",
                "broker_host_sha256": None,
                "raw_locator_in_output": False,
            },
        ]
    )
    monkeypatch.setattr(
        tool,
        "_window_control",
        lambda manager, command, **kwargs: (
            next(states)
        ),
    )
    monkeypatch.setattr(
        tool,
        "_wait_dynamic_closed",
        lambda manager: {},
    )
    monkeypatch.setattr(
        tool,
        "_watchdog_is_active",
        lambda transaction: True,
    )
    monkeypatch.setattr(
        tool,
        "_first_pair_success_evidence",
        lambda system_id: evidence,
    )
    monkeypatch.setattr(
        tool,
        "_db_counts",
        _paired_counts,
    )
    monkeypatch.setattr(
        tool,
        "_security_state_counts",
        _paired_security_counts,
    )
    monkeypatch.setattr(
        tool,
        "_cancel_watchdog",
        lambda transaction: "",
    )

    report = tool.close_window(
        authorization_id=(
            transaction[
                "authorization_id"
            ]
        ),
        confirmation=tool.CLOSE_CONFIRMATION,
        outcome="success",
    )

    assert report["status"] == "PASS"
    assert (
        report["pairing_window_state"]
        == "CLOSED_PASS"
    )
    assert report["manager_recreated"] is False
    assert (
        report["success_evidence"]
        == evidence
    )
    assert (
        tool._transaction()["status"]
        == "CLOSED_PASS"
    )


def test_abort_close_does_not_require_pairing_success_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    _configure_transaction_paths(
        tool,
        tmp_path,
    )
    transaction = _open_transaction(
        tool
    )
    baseline = _runtime_snapshot()

    monkeypatch.setattr(
        tool,
        "_require_root",
        lambda: None,
    )
    monkeypatch.setattr(
        tool,
        "_runtime_snapshot",
        lambda: baseline,
    )
    monkeypatch.setattr(
        tool,
        "_validate_runtime_continuity",
        lambda before, after: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_runtime_configuration",
        lambda snapshot: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_runtime",
        lambda snapshot: None,
    )
    monkeypatch.setattr(
        tool,
        "_window_control",
        lambda manager, command, **kwargs: {
            "accepted": True,
            "code": command,
            "pairing_window_state": (
                "OPEN"
                if command == "status"
                else "CLOSED"
            ),
            "broker_host_sha256": (
                transaction[
                    "broker_host_sha256"
                ]
                if command == "status"
                else None
            ),
            "raw_locator_in_output": False,
        },
    )
    monkeypatch.setattr(
        tool,
        "_wait_dynamic_closed",
        lambda manager: {},
    )
    monkeypatch.setattr(
        tool,
        "_watchdog_is_active",
        lambda transaction: True,
    )
    monkeypatch.setattr(
        tool,
        "_first_pair_success_evidence",
        lambda system_id: (
            pytest.fail(
                "abort must not require success evidence"
            )
        ),
    )
    monkeypatch.setattr(
        tool,
        "_db_counts",
        _zero_counts,
    )
    monkeypatch.setattr(
        tool,
        "_security_state_counts",
        _zero_security_counts,
    )
    monkeypatch.setattr(
        tool,
        "_cancel_watchdog",
        lambda transaction: "",
    )

    report = tool.close_window(
        authorization_id=(
            transaction[
                "authorization_id"
            ]
        ),
        confirmation=tool.CLOSE_CONFIRMATION,
        outcome="abort",
    )

    assert report["status"] == "PASS"
    assert (
        report["pairing_window_state"]
        == "CLOSED_ABORTED"
    )


def test_manager_timeout_is_primary_and_watchdog_only_reconciles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    _configure_transaction_paths(
        tool,
        tmp_path,
    )
    transaction = _open_transaction(
        tool,
        window_seconds=180,
    )
    baseline = _runtime_snapshot()
    monkeypatch.setattr(
        tool.time,
        "time",
        lambda: (
            transaction[
                "expires_at_unix"
            ]
            + 1
        ),
    )

    monkeypatch.setattr(
        tool,
        "_require_root",
        lambda: None,
    )
    monkeypatch.setattr(
        tool,
        "_runtime_snapshot",
        lambda: baseline,
    )
    monkeypatch.setattr(
        tool,
        "_validate_runtime_continuity",
        lambda before, after: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_runtime_configuration",
        lambda snapshot: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_runtime",
        lambda snapshot: None,
    )
    monkeypatch.setattr(
        tool,
        "_window_control",
        lambda manager, command, **kwargs: {
            "accepted": True,
            "code": "status",
            "pairing_window_state": "CLOSED",
            "broker_host_sha256": None,
            "raw_locator_in_output": False,
        },
    )
    monkeypatch.setattr(
        tool,
        "_wait_dynamic_closed",
        lambda manager: {},
    )
    monkeypatch.setattr(
        tool,
        "_listener_count",
        lambda protocol, port: 0,
    )
    monkeypatch.setattr(
        tool,
        "_db_counts",
        _zero_counts,
    )
    monkeypatch.setattr(
        tool,
        "_security_state_counts",
        _zero_security_counts,
    )

    report = tool.expire_window(
        authorization_sha256=(
            tool._sha256_text(
                transaction[
                    "authorization_id"
                ]
            )
        )
    )

    assert report["status"] == "PASS"
    assert (
        report["pairing_window_state"]
        == "CLOSED_TIMEOUT"
    )
    assert report["manager_recreated"] is False


def test_timeout_control_failure_never_restarts_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    _configure_transaction_paths(
        tool,
        tmp_path,
    )
    transaction = _open_transaction(
        tool,
        window_seconds=180,
    )
    baseline = _runtime_snapshot()
    monkeypatch.setattr(
        tool.time,
        "time",
        lambda: (
            transaction[
                "expires_at_unix"
            ]
            + 1
        ),
    )

    monkeypatch.setattr(
        tool,
        "_require_root",
        lambda: None,
    )
    monkeypatch.setattr(
        tool,
        "_runtime_snapshot",
        lambda: baseline,
    )
    monkeypatch.setattr(
        tool,
        "_validate_runtime_continuity",
        lambda before, after: None,
    )
    monkeypatch.setattr(
        tool,
        "_validate_factory_runtime_configuration",
        lambda snapshot: None,
    )
    monkeypatch.setattr(
        tool,
        "_window_control",
        lambda manager, command, **kwargs: (
            (_ for _ in ()).throw(
                tool.OnboardingError(
                    "control_unavailable"
                )
            )
        ),
    )
    monkeypatch.setattr(
        tool,
        "_listener_count",
        lambda protocol, port: 0,
    )

    report = tool.expire_window(
        authorization_sha256=(
            tool._sha256_text(
                transaction[
                    "authorization_id"
                ]
            )
        )
    )

    assert report["status"] == "FAIL"
    assert (
        report["pairing_window_state"]
        == "CLOSED_TIMEOUT_CONTROL_UNAVAILABLE"
    )
    assert report["manager_recreated"] is False


def test_watchdog_runs_after_manager_deadline_without_retry_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    _configure_transaction_paths(
        tool,
        tmp_path,
    )
    transaction = _open_transaction(
        tool
    )
    commands: list[
        tuple[str, ...]
    ] = []
    fake_sha = "e" * 64

    monkeypatch.setattr(
        tool,
        "_prepare_runtime_root",
        lambda transaction: None,
    )
    monkeypatch.setattr(
        tool,
        "_sha256_file",
        lambda path: fake_sha,
    )
    transaction = tool._advance_transaction(
        tool_sha256=fake_sha,
        watchdog_tool_sha256=fake_sha,
    )
    monkeypatch.setattr(
        tool,
        "_run",
        lambda argv, **kwargs: (
            commands.append(
                tuple(argv)
            )
            or ""
        ),
    )
    monkeypatch.setattr(
        tool,
        "_systemctl_is_active",
        lambda unit: True,
    )

    observed = tool._arm_watchdog(
        transaction
    )

    assert observed["watchdog_armed"] is True
    rendered = " ".join(
        commands[0]
    )
    assert "--property=Type=exec" in rendered
    assert "Restart=on-failure" not in rendered
    assert "RestartSec=" not in rendered
    on_active = [
        value
        for value
        in commands[0]
        if value.startswith(
            "--on-active="
        )
    ]
    assert len(on_active) == 1
    seconds = int(
        on_active[0]
        .split("=", 1)[1]
        .rstrip("s")
    )
    assert seconds > 300


def test_runtime_continuity_includes_manager() -> None:
    tool = load_tool()
    before = _runtime_snapshot()
    after = _runtime_snapshot(
        manager_id="d" * 64,
    )

    with pytest.raises(
        tool.OnboardingError,
        match=(
            "manager_container_identity_changed"
        ),
    ):
        tool._validate_runtime_continuity(
            before,
            after,
        )


def test_authorization_is_one_shot_and_strictly_named() -> None:
    tool = load_tool()

    assert (
        tool._authorization_id(
            "N3W_T1_FIRST_PAIRING_"
            "BOARD_D_20261024_02"
        )
        == (
            "N3W_T1_FIRST_PAIRING_"
            "BOARD_D_20261024_02"
        )
    )

    with pytest.raises(
        tool.OnboardingError,
        match="authorization_id_invalid",
    ):
        tool._authorization_id(
            "anything"
        )
