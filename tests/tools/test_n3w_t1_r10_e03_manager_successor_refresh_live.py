from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "n3w_t1_r10_e03_manager_successor_refresh_live.py"
)
SPEC = importlib.util.spec_from_file_location("r10_e03_refresh_live", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
tool = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tool
SPEC.loader.exec_module(tool)


def pre_ledger() -> dict[str, object]:
    return {
        "attempt_count": 1,
        "registration_count": 1,
        "registration_inventory_sha256": tool.PRE_INVENTORY_SHA256,
        "unresolved_count": 1,
        "attempts": [{
            "pairing_id_sha256": tool.PAIRING_SHA256,
            "hardware_id_sha256": tool.HARDWARE_SHA256,
            "state": "ACTIVE",
            "phase": "BOOTSTRAP_ACCEPTED",
            "cleanup_state": "NONE",
            "node_id_present": False,
            "terminal_at_present": False,
            "terminal_reason": None,
            "expired_by_clock": True,
            "session_state": "pending",
            "session_reason": None,
            "session_hardware_sha256": tool.HARDWARE_SHA256,
            "registration_match_count": 1,
            "current_pairing_matches": True,
            "registration_node_id_present": False,
            "pairing_credential_count": 0,
            "hardware_credential_history_count": 0,
        }],
    }


def post_ledger() -> dict[str, object]:
    return {
        "attempt_count": 1,
        "registration_count": 0,
        "registration_inventory_sha256": tool.EMPTY_INVENTORY_SHA256,
        "unresolved_count": 0,
        "attempts": [{
            "pairing_id_sha256": tool.PAIRING_SHA256,
            "hardware_id_sha256": tool.HARDWARE_SHA256,
            "state": "EXPIRED",
            "phase": "TERMINAL",
            "cleanup_state": "COMPLETE",
            "node_id_present": False,
            "terminal_at_present": True,
            "terminal_reason": "expired",
            "expired_by_clock": True,
            "session_state": "expired",
            "session_reason": "expired",
            "session_hardware_sha256": tool.HARDWARE_SHA256,
            "registration_match_count": 0,
            "current_pairing_matches": False,
            "registration_node_id_present": False,
            "pairing_credential_count": 0,
            "hardware_credential_history_count": 0,
        }],
    }


def required_ledger() -> dict[str, object]:
    value = pre_ledger()
    value["attempts"][0].update({
        "state": "EXPIRED",
        "phase": "TERMINAL",
        "cleanup_state": "REQUIRED",
        "terminal_at_present": True,
        "terminal_reason": "expired",
    })
    return value


def test_empty_inventory_hash_is_frozen() -> None:
    assert (
        tool.EMPTY_INVENTORY_SHA256
        == "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    )


def test_pre_ledger_exact_passes() -> None:
    tool.validate_pre_ledger(pre_ledger())


def test_pre_ledger_identity_drift_stops() -> None:
    value = pre_ledger()
    value["attempts"][0]["hardware_id_sha256"] = "0" * 64
    with pytest.raises(tool.RefreshError, match="pre_ledger_state_drift"):
        tool.validate_pre_ledger(value)


def test_post_ledger_exact_passes() -> None:
    tool.validate_post_ledger(post_ledger())


def test_post_registration_count_one_is_never_success() -> None:
    value = post_ledger()
    value["registration_count"] = 1
    value["registration_inventory_sha256"] = tool.PRE_INVENTORY_SHA256
    with pytest.raises(tool.RefreshError, match="post_ledger_cardinality_invalid"):
        tool.validate_post_ledger(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (pre_ledger(), "ORIGINAL_UNRESOLVED"),
        (post_ledger(), "REPAIR_COMPLETE"),
        (required_ledger(), "RESTARTABLE_REQUIRED"),
    ],
)
def test_known_rollback_classifications(
    value: dict[str, object],
    expected: str,
) -> None:
    assert tool.rollback_class(value) == expected


def test_required_with_credential_drift_is_emergency() -> None:
    value = required_ledger()
    value["attempts"][0]["pairing_credential_count"] = 1
    assert tool.rollback_class(value) == "EMERGENCY_STOP"


def test_rewrite_changes_only_manager_image() -> None:
    original = (
        "name: n3wfc4\n"
        "services:\n"
        "  broker:\n"
        "    image: broker\n"
        "  manager:\n"
        f"    image: {tool.OLD_MANAGER_IMAGE}\n"
        "    network_mode: host\n"
        "  homeassistant:\n"
        "    image: ha\n"
    ).encode()
    changed = tool.rewrite_manager_image(original)
    assert changed == original.replace(
        tool.OLD_MANAGER_IMAGE.encode(),
        tool.TARGET_MANAGER_IMAGE.encode(),
    )


def test_rewrite_rejects_wrong_predecessor() -> None:
    with pytest.raises(tool.RefreshError, match="predecessor_drift"):
        tool.rewrite_manager_image(
            b"services:\n  manager:\n    image: wrong\n"
        )


def test_render_validation_allows_only_manager_image() -> None:
    before = {
        "services": {
            "manager": {"image": tool.OLD_MANAGER_IMAGE, "network_mode": "host"},
            "broker": {"image": tool.BROKER_IMAGE},
            "homeassistant": {"image": tool.HA_IMAGE},
        }
    }
    after = json.loads(json.dumps(before))
    after["services"]["manager"]["image"] = tool.TARGET_MANAGER_IMAGE
    tool.validate_candidate(before, after)


def test_render_validation_rejects_broker_drift() -> None:
    before = {
        "services": {
            "manager": {"image": tool.OLD_MANAGER_IMAGE},
            "broker": {"image": tool.BROKER_IMAGE},
        }
    }
    after = json.loads(json.dumps(before))
    after["services"]["manager"]["image"] = tool.TARGET_MANAGER_IMAGE
    after["services"]["broker"]["image"] = "wrong"
    with pytest.raises(tool.RefreshError, match="candidate_non_manager_drift"):
        tool.validate_candidate(before, after)


def test_pr725_head_must_equal_executor_source_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = argparse.Namespace(
        authorization_id="N3W_R10_E03_MANAGER_SUCCESSOR_REFRESH_LIVE_APPLY_20261029_01",
        confirmation=tool.CONFIRMATION,
        executor_source_head="1" * 40,
        executor_blob="2" * 40,
        pr725_head="3" * 40,
    )
    with pytest.raises(tool.RefreshError, match="pr725_executor_head_mismatch"):
        tool.remote_claim(args)


def test_prestop_abort_closes_claimed_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = {
        "schema": tool.TX_SCHEMA,
        "status": "CLAIMED",
        "phase": "AUTHORIZATION_CLAIMED",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "compose_sha256": "1" * 64,
    }
    monkeypatch.setattr(
        tool,
        "transaction_lock",
        lambda: __import__("contextlib").nullcontext(),
    )
    monkeypatch.setattr(tool, "read_tx", lambda: dict(stored))
    monkeypatch.setattr(
        tool,
        "preclaim",
        lambda: {"compose_sha256": "1" * 64},
    )

    def update(doc, phase, **extra):
        stored.update(doc)
        stored.update(extra)
        stored["phase"] = phase

    monkeypatch.setattr(tool, "tx_update", update)
    result = tool.remote_abort_prestop("DOCKER_LOAD_FAILED")
    assert result["transaction_status"] == "FAILED_PRESTOP"
    assert stored["status"] == "FAILED_PRESTOP"
    assert stored["phase"] == "FAILED_PRESTOP"
    assert stored["authorization_consumed"] is True
    assert stored["replay_allowed"] is False


def test_prestop_abort_requires_claimed_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tool,
        "transaction_lock",
        lambda: __import__("contextlib").nullcontext(),
    )
    monkeypatch.setattr(
        tool,
        "read_tx",
        lambda: {
            "schema": tool.TX_SCHEMA,
            "status": "PASS",
            "phase": "COMMITTED",
            "authorization_consumed": True,
            "replay_allowed": False,
        },
    )
    with pytest.raises(tool.RefreshError, match="prestop_abort_state_invalid"):
        tool.remote_abort_prestop("DOCKER_LOAD_FAILED")


def test_authorization_id_is_gate_scoped() -> None:
    value = "N3W_R10_E03_MANAGER_SUCCESSOR_REFRESH_LIVE_APPLY_20261029_01"
    assert tool.authorization_id(value) == value
    with pytest.raises(tool.RefreshError, match="authorization_id_invalid"):
        tool.authorization_id("N3W_OTHER_GATE_01")


def test_claim_is_exclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "tx.json"
    monkeypatch.setattr(tool, "TX_PATH", path)
    monkeypatch.setattr(tool, "require_private_parent", lambda _path: None)
    monkeypatch.setattr(tool.os, "chown", lambda *_args: None)
    tool.write_tx({"schema": tool.TX_SCHEMA}, exclusive=True)
    with pytest.raises(tool.RefreshError, match="authorization_already_claimed"):
        tool.write_tx({"schema": tool.TX_SCHEMA}, exclusive=True)


def test_activation_env_exact_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "broker-activation.env"
    path.write_text(
        "N3WFC4_COMPOSE_FILE=/etc/n3wfc4/docker-compose.yml\n"
        "N3WFC4_COMPOSE_ENV_FILE=/etc/n3wfc4/docker-compose.env\n"
        "N3WFC4_COMPOSE_PROJECT_NAME=n3wfc4\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tool, "BROKER_ENV", path)
    assert tool.parse_activation_env()["N3WFC4_COMPOSE_PROJECT_NAME"] == "n3wfc4"


def test_activation_env_drift_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "broker-activation.env"
    path.write_text(
        "N3WFC4_COMPOSE_FILE=/tmp/wrong.yml\n"
        "N3WFC4_COMPOSE_ENV_FILE=/etc/n3wfc4/docker-compose.env\n"
        "N3WFC4_COMPOSE_PROJECT_NAME=n3wfc4\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tool, "BROKER_ENV", path)
    with pytest.raises(tool.RefreshError, match="activation_env_authority_drift"):
        tool.parse_activation_env()


def test_ha_hash_ignores_non_mqtt_entries(tmp_path: Path) -> None:
    path = tmp_path / "core.config_entries"
    doc = {
        "data": {
            "entries": [
                {"entry_id": "m", "domain": "mqtt", "data": {"host": "a"}},
                {"entry_id": "x", "domain": "sun", "data": {"v": 1}},
            ]
        }
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    before = tool.ha_mqtt_hash(path)
    doc["data"]["entries"][1]["data"]["v"] = 2
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert tool.ha_mqtt_hash(path) == before
    doc["data"]["entries"][0]["data"]["host"] = "b"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert tool.ha_mqtt_hash(path) != before


def test_manager_paths_use_live_bind_mounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = {
        "pairing": "/var/lib/greenhouse-manager/manager/manager-state.sqlite3",
        "credential": "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3",
    }
    monkeypatch.setattr(
        tool,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, json.dumps(settings).encode(), b""
        ),
    )
    monkeypatch.setattr(
        tool,
        "inspect_container",
        lambda _id: {
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": "/var/lib/greenhouse-manager/manager",
                    "Destination": "/var/lib/greenhouse-manager/manager",
                },
                {
                    "Type": "bind",
                    "Source": "/var/lib/greenhouse-manager/n3w",
                    "Destination": "/var/lib/greenhouse-manager/n3w",
                },
            ]
        },
    )
    inside, host = tool.manager_paths("manager")
    assert inside == settings
    assert host == settings


def test_manager_paths_reject_unmapped_live_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = {"pairing": "/x/a.sqlite3", "credential": "/x/b.sqlite3"}
    monkeypatch.setattr(
        tool,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, json.dumps(settings).encode(), b""
        ),
    )
    monkeypatch.setattr(tool, "inspect_container", lambda _id: {"Mounts": []})
    with pytest.raises(tool.RefreshError, match="translation_missing"):
        tool.manager_paths("manager")


def test_artifact_metadata_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "id": tool.TARGET_ARTIFACT_ID,
        "name": tool.TARGET_ARTIFACT_NAME,
        "digest": "sha256:" + tool.TARGET_ARTIFACT_DIGEST,
        "expired": False,
    }
    monkeypatch.setattr(
        tool,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, json.dumps(payload).encode(), b""
        ),
    )
    tool.verify_artifact_metadata()


def test_artifact_metadata_digest_drift_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "id": tool.TARGET_ARTIFACT_ID,
        "name": tool.TARGET_ARTIFACT_NAME,
        "digest": "sha256:" + "0" * 64,
        "expired": False,
    }
    monkeypatch.setattr(
        tool,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, json.dumps(payload).encode(), b""
        ),
    )
    with pytest.raises(tool.RefreshError, match="artifact_metadata_binding_mismatch"):
        tool.verify_artifact_metadata()


def test_local_binding_requires_exact_successor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = tmp_path / "binding.json"
    binding.write_text(
        json.dumps({
            "schema": "gh.n3w.t1-fresh-exact-arm64-binding/1",
            "source_head": tool.TARGET_SOURCE_HEAD,
            "manager": {
                "image": tool.TARGET_MANAGER_IMAGE,
                "image_id": tool.TARGET_MANAGER_ID,
                "tar_sha256": tool.TARGET_MANAGER_TAR_SHA256,
            },
        }),
        encoding="utf-8",
    )
    tar = tmp_path / "manager.tar"
    tar.write_bytes(b"x")
    real = tool.sha_file
    monkeypatch.setattr(
        tool,
        "sha_file",
        lambda path: tool.TARGET_MANAGER_TAR_SHA256 if path == tar else real(path),
    )
    tool.verify_local_artifact(tar, binding)


def test_strict_child_ssh_disables_fallback() -> None:
    class Fake:
        target = "root@192.0.2.1"
        known_hosts = Path("/tmp/known_hosts")
        control_path = Path("/tmp/ctl")

        def assert_master(self) -> None:
            pass

    joined = " ".join(tool.child_ssh_argv(Fake(), ("sudo", "-n", "true")))
    assert "StrictHostKeyChecking=yes" in joined
    assert "BatchMode=yes" in joined
    assert "PasswordAuthentication=no" in joined
    assert "PubkeyAuthentication=no" in joined
    assert "ProxyCommand=/usr/bin/false" in joined


def test_embedded_remote_programs_compile() -> None:
    compile(tool.SETTINGS_PROBE, "<settings-probe>", "exec")
    compile(tool.LEDGER_PROBE, "<ledger-probe>", "exec")


def test_ledger_probe_is_readonly() -> None:
    source = tool.LEDGER_PROBE.upper()
    assert "?MODE=RO" in source
    assert "PRAGMA QUERY_ONLY=ON" in source
    assert "INSERT " not in source
    assert "UPDATE " not in source
    assert "DELETE " not in source


def test_source_contains_nonpersistent_directory_transaction_lock() -> None:
    source = TOOL_PATH.read_text(encoding="utf-8")
    assert "fcntl.LOCK_EX | fcntl.LOCK_NB" in source
    assert "transaction_busy" in source


def test_source_forbids_manager_only_recreate() -> None:
    source = TOOL_PATH.read_text(encoding="utf-8")
    assert "--force-recreate manager" not in source
    assert '("docker", "stop", "manager")' not in source
    assert '("systemctl", "stop", SERVICES_UNIT)' in source
    assert '("systemctl", "start", SERVICES_UNIT)' in source


def test_public_preclaim_hashes_container_identity() -> None:
    value = {
        "compose_sha256": "1" * 64,
        "compose_render_sha256": "2" * 64,
        "target_image_prestate": "ABSENT",
        "runtimes": {
            "manager": {"image_id": tool.OLD_MANAGER_ID},
            "broker": {"container_id": "raw-id"},
        },
        "ha_mqtt_sha256": "3" * 64,
        "ledger": pre_ledger(),
    }
    result = tool.public_preclaim(value)
    encoded = json.dumps(result)
    assert "raw-id" not in encoded
    assert result["commit_classification"] == "DEFINITELY_NOT_COMMITTED"


def test_stop_output_preserves_unknown_authorization(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        tool,
        "host_apply",
        lambda _args: (_ for _ in ()).throw(
            tool.AuthorizationUnknownError("claim_state_unknown")
        ),
    )
    code = tool.main([
        "apply",
        "--t1", "root@192.0.2.1",
        "--known-hosts", "/tmp/known",
        "--host-key-sha256", "1" * 64,
        "--manager-tar", "/tmp/a",
        "--binding-json", "/tmp/b",
        "--authorization-id",
        "N3W_R10_E03_MANAGER_SUCCESSOR_REFRESH_LIVE_APPLY_20261029_01",
        "--confirmation", tool.CONFIRMATION,
        "--executor-source-head", "1" * 40,
        "--executor-blob", "2" * 40,
        "--pr725-head", "3" * 40,
    ])
    assert code == 2
    report = json.loads(capsys.readouterr().out)
    assert report["authorization_consumed"] == "UNKNOWN"
    assert report["replay_allowed"] is False
    assert report["t1_mutation"] == "UNKNOWN"
