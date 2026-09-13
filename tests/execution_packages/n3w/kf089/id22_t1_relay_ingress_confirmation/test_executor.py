from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
IMPL = ROOT / "tools" / "execution_packages" / "n3w" / "kf089" / "id22_t1_relay_ingress_confirmation" / "executor_impl.py"
ENTRY = IMPL.with_name("executor.py")

spec = importlib.util.spec_from_file_location("id22_impl_test", IMPL)
assert spec and spec.loader
impl = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = impl
spec.loader.exec_module(impl)

entry_spec = importlib.util.spec_from_file_location("id22_entry_test", ENTRY)
assert entry_spec and entry_spec.loader
entry = importlib.util.module_from_spec(entry_spec)
sys.modules[entry_spec.name] = entry
entry_spec.loader.exec_module(entry)


def _container_row(
    *,
    service: str,
    cid: str,
    name: str | None = None,
    project: str = "test",
    running: bool = True,
    restart: int = 0,
    network: str = "bridge",
    ports: dict | None = None,
) -> dict:
    return {
        "id": cid,
        "name": "/" + (name or service),
        "image": "local/" + service + ":test",
        "labels": {
            "com.docker.compose.service": service,
            "com.docker.compose.project": project,
        },
        "running": running,
        "restart_count": restart,
        "network_mode": network,
        "ports": ports or {},
    }


def _snapshot_direct() -> dict[str, int]:
    value = {
        "schema_version": 5,
        "boot_session": 100,
        "snapshot_uptime_ms": 200000,
        "path_state": 0,
        "current_channel": 11,
        "direct_channel_hint": 11,
        "relay_active_count": 0,
        "relay_telemetry_attempts": 0,
        "relay_telemetry_success": 0,
        "accept_verify": 0,
        "peer_install_success": 0,
        "unicast_completion_count": 0,
        "unicast_completion_success": 0,
        "unicast_completion_failure": 0,
    }
    for field in impl.id21.COMPACT_FIELDS:
        value[field] = 0
    return value


def _snapshot_a_relay() -> dict[str, int]:
    value = _snapshot_direct()
    value["boot_session"] = 101
    value["compact_rx_count"] = 3
    value["compact_decode_success"] = 3
    value["compact_forward_attempts"] = 3
    value["compact_forward_submit_success"] = 3
    return value


def _snapshot_b_relay() -> dict[str, int]:
    value = _snapshot_direct()
    value.update(
        {
            "boot_session": 201,
            "path_state": 2,
            "relay_active_count": 1,
            "accept_verify": 1,
            "peer_install_success": 1,
            "relay_telemetry_attempts": 4,
            "relay_telemetry_success": 4,
            "unicast_completion_count": 4,
            "unicast_completion_success": 3,
            "unicast_completion_failure": 1,
        }
    )
    return value


def _healthy_runtime_rows() -> list[dict]:
    return [
        _container_row(
            service="greenhouse-manager",
            name="greenhouse-manager",
            cid="m1",
            project="manager-successor",
            network="host",
        ),
        _container_row(
            service="broker",
            name="fc4-broker",
            cid="b1",
            project="n3wfc4",
            ports={"8883/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8883"}]},
        ),
        _container_row(service="homeassistant", name="fc4-homeassistant", cid="h1"),
    ]


def test_self_check() -> None:
    impl.self_check()
    entry.self_check()


def test_current_t1_runtime_classifier_accepts_authoritative_manager_broker() -> None:
    result = entry._classify_current_t1_runtime(impl, _healthy_runtime_rows())
    assert result["manager"]["id"] == "m1"
    assert result["broker"]["id"] == "b1"


def test_current_t1_runtime_classifier_rejects_legacy_manager_service_name() -> None:
    rows = _healthy_runtime_rows()
    rows[0]["labels"]["com.docker.compose.service"] = "manager"
    try:
        entry._classify_current_t1_runtime(impl, rows)
    except impl.StopExecution:
        return
    raise AssertionError("legacy Manager service selector must fail closed")


def test_current_t1_runtime_classifier_rejects_manager_container_name_mismatch() -> None:
    rows = _healthy_runtime_rows()
    rows[0]["name"] = "/other-manager"
    try:
        entry._classify_current_t1_runtime(impl, rows)
    except impl.StopExecution:
        return
    raise AssertionError("Manager container-name mismatch must fail closed")


def test_current_t1_runtime_classifier_rejects_duplicate_authoritative_manager() -> None:
    rows = _healthy_runtime_rows()
    rows.insert(
        1,
        _container_row(
            service="greenhouse-manager",
            name="greenhouse-manager",
            cid="m2",
            project="manager-successor",
            network="host",
        ),
    )
    try:
        entry._classify_current_t1_runtime(impl, rows)
    except impl.StopExecution:
        return
    raise AssertionError("duplicate authoritative Manager must fail closed")


def test_runtime_classifier_installer_replaces_stale_impl_selector() -> None:
    entry._install_current_t1_runtime_classifier(impl)
    result = impl.classify_t1_runtime(_healthy_runtime_rows())
    assert result["manager"]["id"] == "m1"
    assert result["broker"]["id"] == "b1"


def test_manager_relay_log_parser_positive() -> None:
    text = (
        "2026-09-13T00:00:01Z Accepted simplified N3-W telemetry source=relay node=x gateway=y key=1\n"
        "2026-09-13T00:00:02Z Rejected simplified N3-W ingress source=relay node=x gateway=y code=z\n"
        "2026-09-13T00:00:03Z Accepted simplified N3-W telemetry source=direct node=x gateway=None key=2\n"
    )
    assert len(impl.ACCEPTED_RELAY_RE.findall(text)) == 1
    assert len(impl.REJECTED_RELAY_RE.findall(text)) == 1


def test_board_relay_adjudication_same_fresh_session_passes() -> None:
    result = impl.id21.adjudicate_relay_phase(
        a=_snapshot_a_relay(),
        b=_snapshot_b_relay(),
        baseline_a_boot_session=100,
        baseline_b_boot_session=200,
    )
    assert result["board_side_relay_chain_proven"] is True
    assert result["first_unproven_stage"] is None


def test_t1_stability_requires_same_ids_and_restart_counts() -> None:
    pre = {
        "manager": _container_row(
            service="greenhouse-manager",
            name="greenhouse-manager",
            cid="m1",
            network="host",
            restart=0,
        ),
        "broker": _container_row(
            service="broker",
            name="fc4-broker",
            cid="b1",
            restart=0,
            ports={"8883/tcp": [{}]},
        ),
    }
    post = json.loads(json.dumps(pre))
    stable = impl.t1_stability(pre, post)
    assert all(stable.values())
    post["manager"]["restart_count"] = 1
    assert impl.t1_stability(pre, post)["manager_restart_count_unchanged"] is False


def test_manifest_forbids_t1_mutation_and_second_boot() -> None:
    manifest = impl.load_manifest()
    refs = manifest["authority_references"]
    assert refs["manager_container_name"] == "greenhouse-manager"
    assert refs["manager_compose_service"] == "greenhouse-manager"
    assert refs["broker_compose_service"] == "broker"
    forbidden = manifest["forbidden"]
    for key in (
        "t1_file_write",
        "t1_docker_mutation",
        "t1_network_mutation",
        "mqtt_test_publish",
        "mqtt_extra_subscriber",
        "second_normal_boot",
        "automatic_retry",
    ):
        assert forbidden[key] is True
