from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools import n3w_t1_clean_reference_pairing_readiness_bridge as bridge
from tools import (
    n3w_t1_clean_reference_pairing_readiness_bridge_package_builder as builder,
)

CONTROL_HEAD = "7" * 40


def _runtime() -> dict:
    return {
        "boot_id_sha256": "1" * 64,
        "containers": {
            "broker": {
                "container_id_sha256": "a" * 64,
                "started_at": "b-start",
                "restart_count": 0,
            },
            "homeassistant": {
                "container_id_sha256": "b" * 64,
                "started_at": "h-start",
                "restart_count": 0,
            },
            "manager": {
                "container_id_sha256": "c" * 64,
                "started_at": "m-start",
                "restart_count": 0,
            },
        },
        "sqlite": {
            "/manager.db": {
                "row_counts": {
                    "registrations": 0,
                    "pairing_sessions": 0,
                },
                "file_bytes": 4096,
                "wal_bytes": 0,
            }
        },
        "dynsec_counts": {
            "clients": 4,
            "groups": 1,
            "roles": 10,
        },
        "homeassistant_registry_counts": {
            "entities": {"present": True, "count": 14, "version": 1},
            "devices": {"present": True, "count": 3, "version": 3},
            "config_entries": {"present": True, "count": 6, "version": 1},
        },
        "mqtt_session": {
            "manager": {
                "count": 1,
                "identity_sha256": "d" * 64,
                "authenticated_event_count": 1,
                "fingerprint": "e" * 64,
            },
            "homeassistant": {
                "count": 1,
                "identity_sha256": "f" * 64,
                "authenticated_event_count": 5,
                "fingerprint": "0" * 64,
            },
        },
        "persistent_tree_stats": {
            "/state": {
                "file_count": 1,
                "directory_count": 1,
                "total_bytes": 100,
                "symlink_count": 0,
            }
        },
    }


def _reference() -> dict:
    return {
        "schema": "gh.n3w-t1-clean-reference-observation/1",
        "status": "PASS",
        "reference_label": "R2",
        "stable_contracts": {
            "authority": {
                "product_source_head": bridge.PRODUCT_SOURCE_HEAD,
                "r2a_control_head": bridge.R2A_CONTROL_HEAD,
                "r2b_control_head": bridge.R2B_CONTROL_HEAD,
                "r2a_transaction_sha256": "2" * 64,
                "r2b_transaction_sha256": "3" * 64,
            },
            "component_identity": {
                "broker": {"image": "broker"},
                "homeassistant": {"image": "ha"},
                "manager": {"image": "manager"},
            },
        },
        "health": {
            "overall_pass": True,
            "failed_unit_count": 0,
        },
        "runtime_observations": _runtime(),
        "read_only": True,
        "network_mutation": False,
        "board_access": False,
    }


def _test_private_writer(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _relax_runner_root_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_read_json = bridge._read_json

    def relaxed_read_json(path: Path, *, mode: int | None = None) -> dict:
        return real_read_json(path, mode=None)

    monkeypatch.setattr(bridge, "_read_json", relaxed_read_json)


def _preflight() -> dict:
    return {
        "manifest": {
            "control_plane_head": CONTROL_HEAD,
        },
        "transactions": {
            "r2a_transaction_sha256": "2" * 64,
            "r2b_transaction_sha256": "3" * 64,
        },
        "identity": {
            "release_id": bridge.PRODUCT_SOURCE_HEAD,
            "host_instance_id": "t1h-example",
            "system_id": "system-example",
            "host_instance_id_sha256": "4" * 64,
            "system_id_sha256": "5" * 64,
            "system_identity_manifest_sha256": "6" * 64,
            "identity_authority": "clean_reference_runtime_identity_v1",
            "device_provisioning_state": "UNPROVISIONED",
        },
        "registration": {
            "registration_ready": True,
            "registration_bootstrap_listener_count": 1,
            "registration_discovery_listener_count": 1,
            "privileged_pairing_listener_count": 0,
            "pairing_window_state": "CLOSED",
            "trusted_network_sha256": "7" * 64,
            "trusted_lan_generation_sha256": "8" * 64,
            "registration_guard_applied": True,
            "registration_guard_anchor_positions": [2, 3, 4],
        },
        "current": _reference(),
    }


def test_package_builder_emits_bridge_and_exact_observer(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    destination = tmp_path / "package"

    report = builder.build_package(repo_root, destination, CONTROL_HEAD)

    assert report["status"] == "PASS"
    assert report["file_count"] == 2
    manifest = json.loads(
        (destination / "package-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == builder.SCHEMA
    assert manifest["product_source_head"] == bridge.PRODUCT_SOURCE_HEAD
    assert manifest["r2a_control_head"] == bridge.R2A_CONTROL_HEAD
    assert manifest["r2b_control_head"] == bridge.R2B_CONTROL_HEAD
    assert (
        manifest["r3_observer_control_head"]
        == bridge.R3_OBSERVER_CONTROL_HEAD
    )
    assert manifest["r2_reference_sha256"] == bridge.R2_REFERENCE_SHA256
    assert manifest["control_plane_head"] == CONTROL_HEAD
    assert {row["path"] for row in manifest["files"]} == set(builder.FILES)


def test_relevant_runtime_ignores_persistent_size_but_not_business_state() -> None:
    baseline = _reference()
    current = _reference()

    current["runtime_observations"]["persistent_tree_stats"]["/state"][
        "total_bytes"
    ] = 9999

    assert bridge._relevant_runtime(current) == bridge._relevant_runtime(baseline)

    current["runtime_observations"]["sqlite"]["/manager.db"]["row_counts"][
        "registrations"
    ] = 1

    assert bridge._relevant_runtime(current) != bridge._relevant_runtime(baseline)


def test_factory_document_is_standard_compatible_and_provenance_bound() -> None:
    document = bridge._factory_document(_preflight())

    assert document["schema"] == "gh.n3w.t1-factory-accepted/1"
    assert document["status"] == "PASS"
    assert document["factory_accepted"] is True
    assert document["release_id"] == bridge.PRODUCT_SOURCE_HEAD
    assert document["host_instance_id"] == "t1h-example"
    assert document["system_id"] == "system-example"
    assert document["system_id_sha256"] == "5" * 64
    assert document["acceptance_route"] == "clean_reference_r2_bridge_v2"
    assert document["identity_authority"] == "clean_reference_runtime_identity_v1"
    assert document["device_provisioning_state"] == "UNPROVISIONED"
    assert document["system_identity_manifest_sha256"] == "6" * 64
    assert document["r2_reference_sha256"] == bridge.R2_REFERENCE_SHA256
    assert document["r2a_transaction_sha256"] == "2" * 64
    assert document["r2b_transaction_sha256"] == "3" * 64
    assert document["bridge_control_head"] == CONTROL_HEAD


def test_parser_exposes_readonly_commands_only() -> None:
    parser = bridge._parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, bridge.argparse._SubParsersAction)
    )
    assert set(subparsers.choices) == {"inspect", "status"}


def test_preexisting_bridge_state_blocks_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "bridge-state"
    state_root.mkdir()
    monkeypatch.setattr(bridge, "BRIDGE_ROOT", state_root)
    monkeypatch.setattr(bridge.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        bridge,
        "_package",
        lambda _root: {"control_plane_head": CONTROL_HEAD},
    )

    with pytest.raises(bridge.BridgeError, match="bridge_transaction_already_claimed"):
        bridge._preflight(tmp_path, tmp_path / "r2-reference.json")


def test_clean_security_state_is_required() -> None:
    bridge._require_clean_security_state(
        {
            "credential_assignments": 0,
            "peer_trust_records": 0,
            "application_key_active_nodes": 0,
            "application_key_epochs": 0,
        }
    )

    with pytest.raises(bridge.BridgeError, match="first_pair_security_state_not_clean"):
        bridge._require_clean_security_state(
            {
                "credential_assignments": 1,
                "peer_trust_records": 0,
                "application_key_active_nodes": 0,
                "application_key_epochs": 0,
            }
        )


def test_authorization_contract_is_bounded() -> None:
    valid = bridge.AUTHORIZATION_PREFIX + "HOST_MARKER_20261101_01"
    assert bridge._authorization(valid) == valid

    with pytest.raises(bridge.BridgeError, match="authorization_id_invalid"):
        bridge._authorization("OTHER_AUTHORIZATION")


def test_bridge_source_cannot_reboot_restart_pair_or_touch_board() -> None:
    source = Path(bridge.__file__).read_text(encoding="utf-8")

    forbidden = (
        "systemctl reboot",
        "systemctl restart",
        "docker compose up",
        "docker compose down",
        "docker pull",
        "docker build",
        "esptool",
        "erase-region",
        "OPEN FIRST PAIRING WINDOW",
        "CLOSE FIRST PAIRING WINDOW",
    )

    for token in forbidden:
        assert token not in source

    assert '"inspect"' in source
    assert '"network_mutation": False' in source
    assert '"service_restart": False' in source
    assert '"board_access": False' in source
    assert '"factory_accepted_required": False' in source
    assert 'HOST_TRUSTED_LAN_ROOT = Path("/run/n3wfc4-trusted-lan")' in source
    assert 'MANAGER_TRUSTED_LAN_TARGET = Path("/run/n3w/trusted-product-lan")' in source
    assert 'TRUSTED_LAN_AUTHORITY_TOOL = Path("/usr/local/sbin/n3w-trusted-product-lan-authority")' in source
    assert 'REGISTRATION_GUARD_TOOL = Path("/usr/local/sbin/n3w-registration-ingress-guard")' in source
    assert 'BROKER_GUARD_TOOL = Path("/usr/local/sbin/n3w-broker-ingress-guard")' in source



def test_listener_count_reads_local_address_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        argv: tuple[str, ...],
        *,
        timeout: float = 60.0,
        allowed: frozenset[int] = frozenset({0}),
    ) -> str:
        del timeout, allowed
        if argv == ("ss", "-H", "-lun"):
            return (
                "UNCONN 0 0 0.0.0.0:47111 0.0.0.0:*\n"
                "UNCONN 0 0 0.0.0.0:5353 0.0.0.0:*\n"
            )
        if argv == ("ss", "-H", "-ltn"):
            return (
                "LISTEN 0 128 127.0.0.1:47112 0.0.0.0:*\n"
                "LISTEN 0 128 127.0.0.1:8883 0.0.0.0:*\n"
            )
        raise AssertionError(argv)

    monkeypatch.setattr(bridge, "_run", fake_run)

    assert bridge._listener_count("udp", bridge.REGISTRATION_DISCOVERY_PORT) == 1
    assert bridge._listener_count("tcp", bridge.PRIVILEGED_PAIRING_PORT) == 1


def test_listener_count_does_not_match_peer_address_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        argv: tuple[str, ...],
        *,
        timeout: float = 60.0,
        allowed: frozenset[int] = frozenset({0}),
    ) -> str:
        del argv, timeout, allowed
        return "UNCONN 0 0 0.0.0.0:5353 0.0.0.0:47111\n"

    monkeypatch.setattr(bridge, "_run", fake_run)

    assert bridge._listener_count("udp", bridge.REGISTRATION_DISCOVERY_PORT) == 0


def test_load_registration_guard_supports_extensionless_installed_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    installed_registration = tmp_path / "n3w-registration-ingress-guard"
    installed_broker = tmp_path / "n3w-broker-ingress-guard"

    installed_registration.write_bytes(
        (repo_root / "tools/n3w_registration_ingress_guard.py").read_bytes()
    )
    installed_broker.write_bytes(
        (repo_root / "tools/n3w_broker_ingress_guard.py").read_bytes()
    )

    monkeypatch.setattr(
        bridge,
        "REGISTRATION_GUARD_TOOL",
        installed_registration,
    )
    monkeypatch.setattr(
        bridge,
        "BROKER_GUARD_TOOL",
        installed_broker,
    )
    sys.modules.pop("n3w_broker_ingress_guard", None)

    module = bridge._load_registration_guard()

    assert module.SCHEMA == "gh.n3w-registration-ingress-guard/1"
    assert module.PORT_RULES == (
        ("tcp", 47110),
        ("udp", 47111),
        ("tcp", 47112),
    )


def test_runtime_guard_tools_bind_to_installed_product_paths() -> None:
    assert bridge.TRUSTED_LAN_AUTHORITY_TOOL == Path(
        "/usr/local/sbin/n3w-trusted-product-lan-authority"
    )
    assert bridge.REGISTRATION_GUARD_TOOL == Path(
        "/usr/local/sbin/n3w-registration-ingress-guard"
    )
    assert bridge.BROKER_GUARD_TOOL == Path(
        "/usr/local/sbin/n3w-broker-ingress-guard"
    )


def test_manager_trusted_lan_mount_requires_exact_readonly_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.dumps(
        [
            {
                "Type": "bind",
                "Source": str(bridge.HOST_TRUSTED_LAN_ROOT),
                "Destination": str(bridge.MANAGER_TRUSTED_LAN_TARGET),
                "RW": False,
            }
        ]
    )

    monkeypatch.setattr(
        bridge,
        "_run",
        lambda argv, **_kwargs: payload
        if argv[:4] == ("docker", "inspect", "-f", "{{json .Mounts}}")
        else (_ for _ in ()).throw(AssertionError(argv)),
    )

    bridge._manager_trusted_lan_mount("manager")


def test_manager_trusted_lan_mount_rejects_writable_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.dumps(
        [
            {
                "Type": "bind",
                "Source": str(bridge.HOST_TRUSTED_LAN_ROOT),
                "Destination": str(bridge.MANAGER_TRUSTED_LAN_TARGET),
                "RW": True,
            }
        ]
    )

    monkeypatch.setattr(
        bridge,
        "_run",
        lambda _argv, **_kwargs: payload,
    )

    with pytest.raises(bridge.BridgeError, match="manager_trusted_lan_mount_invalid"):
        bridge._manager_trusted_lan_mount("manager")


def test_trusted_lan_authority_reads_host_runtime_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Path] = []

    def fake_read_json(path: Path, *, mode: int | None = None) -> dict:
        del mode
        seen.append(path)
        return {
            "schema": "gh.trusted-product-lan/1",
            "interface": "eth0",
            "available": True,
            "generation": "generation-1",
            "subnet": "192.168.68.0/24",
        }

    monkeypatch.setattr(bridge, "_read_json", fake_read_json)
    monkeypatch.setattr(
        bridge,
        "_run",
        lambda argv, **_kwargs: json.dumps(
            [
                {
                    "addr_info": [
                        {
                            "family": "inet",
                            "scope": "global",
                            "local": "192.168.68.194",
                        }
                    ]
                }
            ]
        )
        if argv[:5] == ("ip", "-j", "-4", "addr", "show")
        else (_ for _ in ()).throw(AssertionError(argv)),
    )

    report = bridge._trusted_lan_authority()

    assert seen == [bridge.HOST_TRUSTED_LAN_STATE]
    assert report["trusted_network_sha256"]


def test_current_product_registration_readiness_accepts_registration_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge, "_manager_id", lambda: "manager")
    monkeypatch.setattr(bridge, "_manager_trusted_lan_mount", lambda _manager: None)
    monkeypatch.setattr(bridge, "_manager_runtime_flags", lambda _manager: None)
    monkeypatch.setattr(
        bridge,
        "_pairing_control_closed",
        lambda _manager: {"pairing_window_state": "CLOSED"},
    )
    monkeypatch.setattr(
        bridge,
        "_listener_count",
        lambda protocol, port: {
            ("tcp", bridge.REGISTRATION_BOOTSTRAP_PORT): 1,
            ("udp", bridge.REGISTRATION_DISCOVERY_PORT): 1,
            ("tcp", bridge.PRIVILEGED_PAIRING_PORT): 0,
        }[(protocol, port)],
    )
    monkeypatch.setattr(
        bridge,
        "_trusted_lan_authority",
        lambda: {
            "trusted_network_sha256": "a" * 64,
            "trusted_lan_generation_sha256": "b" * 64,
        },
    )
    monkeypatch.setattr(
        bridge,
        "_registration_guard_authority",
        lambda network_hash: {
            "registration_guard_applied": network_hash == "a" * 64,
            "registration_guard_anchor_positions": [2, 3, 4],
        },
    )

    report = bridge._current_product_registration_readiness()

    assert report["registration_ready"] is True
    assert report["registration_bootstrap_listener_count"] == 1
    assert report["registration_discovery_listener_count"] == 1
    assert report["privileged_pairing_listener_count"] == 0
    assert report["pairing_window_state"] == "CLOSED"
    assert report["registration_guard_applied"] is True


def test_current_product_registration_readiness_rejects_privileged_pairing_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge, "_manager_id", lambda: "manager")
    monkeypatch.setattr(bridge, "_manager_trusted_lan_mount", lambda _manager: None)
    monkeypatch.setattr(bridge, "_manager_runtime_flags", lambda _manager: None)
    monkeypatch.setattr(
        bridge,
        "_pairing_control_closed",
        lambda _manager: {"pairing_window_state": "CLOSED"},
    )
    monkeypatch.setattr(
        bridge,
        "_listener_count",
        lambda protocol, port: {
            ("tcp", bridge.REGISTRATION_BOOTSTRAP_PORT): 1,
            ("udp", bridge.REGISTRATION_DISCOVERY_PORT): 1,
            ("tcp", bridge.PRIVILEGED_PAIRING_PORT): 1,
        }[(protocol, port)],
    )

    with pytest.raises(bridge.BridgeError, match="privileged_pairing_listener_present"):
        bridge._current_product_registration_readiness()


def test_missing_provisioning_root_is_valid_unprovisioned_pairing_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "provisioning"
    monkeypatch.setattr(bridge, "PROVISIONING_ROOT", root)
    monkeypatch.setattr(bridge, "FACTORY_ACCEPTED", root / "FACTORY_ACCEPTED.json")
    monkeypatch.setattr(
        bridge,
        "FIRST_PAIRING_TRANSACTION",
        root / "FIRST_PAIRING_ONBOARDING.json",
    )
    monkeypatch.setattr(
        bridge,
        "SUCCESSOR_RECOVERY",
        root / "FIRST_PAIRING_SUCCESSOR_RECOVERY.json",
    )

    assert bridge._pairing_records_absent() is False
    assert root.exists() is False


def test_security_state_counts_executes_real_sqlite_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import sqlite3

    credential = tmp_path / "credential.sqlite3"
    peer = tmp_path / "peer.sqlite3"
    application = tmp_path / "application.sqlite3"

    connection = sqlite3.connect(credential)
    connection.execute("CREATE TABLE credential_assignments (node_id TEXT)")
    connection.commit()
    connection.close()

    connection = sqlite3.connect(peer)
    connection.execute("CREATE TABLE n3w_system_peer_trust (node_id TEXT)")
    connection.commit()
    connection.close()

    connection = sqlite3.connect(application)
    connection.execute("CREATE TABLE n3w_relay_meta (id INTEGER)")
    connection.execute("CREATE TABLE n3w_relay_nodes (active INTEGER)")
    connection.execute("CREATE TABLE n3w_relay_key_epochs (epoch INTEGER)")
    connection.commit()
    connection.close()

    monkeypatch.setattr(bridge, "CREDENTIAL_DB", credential)
    monkeypatch.setattr(bridge, "PEER_TRUST_DB", peer)
    monkeypatch.setattr(bridge, "APPLICATION_KEY_DB", application)

    assert bridge._security_state_counts() == {
        "credential_assignments": 0,
        "peer_trust_records": 0,
        "application_key_active_nodes": 0,
        "application_key_epochs": 0,
    }


def test_device_identity_uses_unprovisioned_status_not_device_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(bridge, "_tool_binding", lambda: None)
    monkeypatch.setattr(
        bridge,
        "_release_binding",
        lambda: bridge.PRODUCT_SOURCE_HEAD,
    )
    monkeypatch.setattr(
        bridge,
        "_host_identity",
        lambda: {
            "host_instance_id": "t1h-runtime",
            "host_instance_id_sha256": "a" * 64,
        },
    )
    monkeypatch.setattr(
        bridge,
        "_system_identity_authority",
        lambda: {
            "system_id": "ghs-runtime",
            "system_id_sha256": "b" * 64,
            "system_identity_manifest_sha256": "c" * 64,
        },
    )

    def run(argv, **_kwargs):
        calls.append(tuple(argv))
        return json.dumps(
            {
                "status": "PASS",
                "state": "UNPROVISIONED",
                "release_id": bridge.PRODUCT_SOURCE_HEAD,
                "production_service_start": False,
                "board_access": False,
            }
        )

    monkeypatch.setattr(bridge, "_run", run)
    identity = bridge._device_identity()

    assert calls == [
        ("python3", str(bridge.DEVICE_PROVISIONING_TOOL), "status")
    ]
    assert identity["device_provisioning_state"] == "UNPROVISIONED"
    assert identity["identity_authority"] == "clean_reference_runtime_identity_v1"


def test_device_identity_rejects_fake_device_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge, "_tool_binding", lambda: None)
    monkeypatch.setattr(
        bridge,
        "_release_binding",
        lambda: bridge.PRODUCT_SOURCE_HEAD,
    )
    monkeypatch.setattr(
        bridge,
        "_run",
        lambda *_args, **_kwargs: json.dumps(
            {
                "status": "PASS",
                "state": "DEVICE_READY",
                "release_id": bridge.PRODUCT_SOURCE_HEAD,
                "production_service_start": False,
                "board_access": False,
            }
        ),
    )

    with pytest.raises(bridge.BridgeError, match="device_provisioning_state_invalid"):
        bridge._device_identity()


def test_host_identity_matches_frozen_os_identity_algorithm(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import hashlib

    machine = tmp_path / "machine-id"
    ssh = tmp_path / "ssh_host_ed25519_key.pub"
    machine_id = "1" * 32
    ssh_public = b"ssh-ed25519 AAAATEST host"
    machine.write_text(machine_id + "\n", encoding="utf-8")
    ssh.write_bytes(ssh_public + b"\n")
    monkeypatch.setattr(bridge, "MACHINE_ID_PATH", machine)
    monkeypatch.setattr(bridge, "SSH_HOST_PUBLIC_KEY", ssh)

    digest = hashlib.sha256(
        machine_id.encode("ascii") + b"\0" + ssh_public
    ).hexdigest()
    expected = f"t1h-{digest[:24]}"
    identity = bridge._host_identity()

    assert identity["host_instance_id"] == expected
    assert identity["host_instance_id_sha256"] == hashlib.sha256(
        expected.encode()
    ).hexdigest()


def test_system_identity_authority_binds_initialization_and_manager_db(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import hashlib
    import os
    import sqlite3

    root = tmp_path / "identity"
    root.mkdir(mode=0o700)
    system_id = "ghs-0123456789abcdef"
    manager_id = "ghm-0123456789abcdef"
    payloads = {
        "system-identity.json": json.dumps(
            {
                "schema": "gh.h0h1.system-identity/1",
                "system_id": system_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode() + b"\n",
        "system-root.key": b"root-key\n",
        "system-ca.pem": b"certificate\n",
        "system-ca-key.pem": b"private-key\n",
        "manager-identity.json": json.dumps(
            {
                "schema": "gh.h0h1.manager-identity/1",
                "system_id": system_id,
                "manager_id": manager_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode() + b"\n",
    }
    files = {}
    for name, payload in payloads.items():
        path = root / name
        path.write_bytes(payload)
        os.chmod(path, 0o600)
        files[name] = {
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    marker = {
        "schema": "gh.h0h1.system-initialization/1",
        "system_id": system_id,
        "manager_id": manager_id,
        "files": files,
    }
    canonical = json.dumps(
        marker,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    marker["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    marker_path = root / "INITIALIZED.json"
    marker_path.write_text(
        json.dumps(marker, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.chmod(marker_path, 0o600)

    manager_db = tmp_path / "manager-state.sqlite3"
    connection = sqlite3.connect(manager_db)
    connection.execute(
        "CREATE TABLE h0h1_legacy_adoption_provenance ("
        "schema TEXT, system_id_fingerprint TEXT, "
        "structured_legacy_manager_state_imported INTEGER, "
        "anonymous_nodes_reconstructed INTEGER)"
    )
    system_sha = hashlib.sha256(system_id.encode()).hexdigest()
    connection.execute(
        "INSERT INTO h0h1_legacy_adoption_provenance VALUES (?, ?, 0, 0)",
        ("gh.h0h1.legacy-adoption-provenance/1", system_sha[:24]),
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(bridge, "SYSTEM_IDENTITY_ROOT", root)
    monkeypatch.setattr(bridge, "SYSTEM_IDENTITY_MARKER", marker_path)
    monkeypatch.setattr(bridge, "SYSTEM_IDENTITY", root / "system-identity.json")
    monkeypatch.setattr(bridge, "MANAGER_IDENTITY", root / "manager-identity.json")
    monkeypatch.setattr(bridge, "MANAGER_DB", manager_db)
    monkeypatch.setattr(bridge, "_require_private_root", lambda path: None)

    authority = bridge._system_identity_authority()
    assert authority["system_id"] == system_id
    assert authority["system_id_sha256"] == system_sha
    assert authority["system_identity_manifest_sha256"] == marker[
        "manifest_sha256"
    ]


